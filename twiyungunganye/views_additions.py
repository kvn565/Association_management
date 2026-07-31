"""
Fichier : views_additions.py
Description : Fonctions supplémentaires à ajouter dans views.py
Ces fonctions remplacent ou complètent les vues existantes
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from decimal import Decimal

from .models import Credit, Association, Notification
from .forms import CreditApprovalForm


def is_admin_only(user):
    return user.is_authenticated and user.is_admin


def get_tenant(request):
    return getattr(request, 'tenant', None)


def qs_for_tenant(request, qs, field='tenant'):
    tenant = get_tenant(request)
    if tenant and not getattr(request, 'is_superadmin', False):
        return qs.filter(**{field: tenant})
    return qs


@login_required
@user_passes_test(is_admin_only)
def approuver_credit_strict(request, pk):
    """
    Approuver ou rejeter un crédit avec VALIDATION STRICTE des fonds
    
    LOGIQUE :
    Fonds disponibles = (Cotisations + Imprévus + Remboursements + Intérêts perçus) 
                      - (Dépenses + Crédits en cours)
    """
    tenant = get_tenant(request)
    credit = get_object_or_404(qs_for_tenant(request, Credit.objects.all()), pk=pk)
    association = Association.get_association(tenant)
    
    if not association:
        messages.error(request, "⚠️ Erreur : Association non configurée.")
        return redirect('liste_credits')
    
    # ÉTAPE 1 : Calculer le total des entrées
    from django.db.models import Sum
    from .models import Cotisation, CotisationImprevu, Remboursement, Depense, Interet
    qs = lambda m: qs_for_tenant(request, m.objects.all())
    total_cotisations = qs(Cotisation).filter(statut='PAYE').aggregate(Sum('montant'))['montant__sum'] or Decimal('0')
    total_imprevus = qs(CotisationImprevu).filter(statut='PAYE').aggregate(Sum('montant'))['montant__sum'] or Decimal('0')
    total_remb_principal = qs(Remboursement).aggregate(Sum('montant_rembourse'))['montant_rembourse__sum'] or Decimal('0')
    total_remb_interets = qs(Interet).filter(date_remboursement__isnull=False).aggregate(Sum('interet_rembourse'))['interet_rembourse__sum'] or Decimal('0')
    total_entrees = total_cotisations + total_imprevus + total_remb_principal + total_remb_interets
    
    # ÉTAPE 2 : Calculer les sorties (dépenses + crédits en cours)
    total_depenses = qs(Depense).aggregate(Sum('montant'))['montant__sum'] or Decimal('0')
    credits_en_cours = qs_for_tenant(request, Credit.objects.filter(
        statut__in=['APPROUVE', 'EN_COURS']
    )).exclude(pk=credit.pk)
    total_credits_accordes = Decimal('0')
    for c in credits_en_cours:
        total_credits_accordes += c.montant_accorde
    total_sorties = total_depenses + total_credits_accordes
    
    # ÉTAPE 3 : Calculer les fonds disponibles
    fonds_disponibles = total_entrees - total_sorties
    
    if request.method == 'POST':
        form = CreditApprovalForm(request.POST, instance=credit, tenant=tenant)
        
        if form.is_valid():
            # Récupérer le montant qu'on veut accorder
            montant_accorde = form.cleaned_data['montant_accorde']
            nouveau_statut = form.cleaned_data['statut']
            
            # VALIDATION STRICTE : Vérifier si on a assez de fonds
            if nouveau_statut == 'APPROUVE' and montant_accorde > fonds_disponibles:
                messages.error(
                    request,
                    f"❌ FONDS INSUFFISANTS ! "
                    f"Vous ne pouvez pas accorder ce crédit. "
                    f"Fonds disponibles : {fonds_disponibles:,.2f} FBU | "
                    f"Montant demandé : {montant_accorde:,.2f} FBU | "
                    f"Manque : {(montant_accorde - fonds_disponibles):,.2f} FBU"
                )
                
                # Afficher les détails
                messages.info(
                    request,
                    f"📊 Détails : "
                    f"Total entrées (cotisations+imprévus+remboursements) = {total_entrees:,.2f} FBU | "
                    f"Total sorties (dépenses+crédits) = {total_sorties:,.2f} FBU"
                )
                
                return redirect('approuver_credit', pk=credit.pk)
            
            # Si validation OK ou si c'est un rejet, sauvegarder
            form.save()
            
            if nouveau_statut == 'APPROUVE':
                nouveaux_fonds = fonds_disponibles - montant_accorde
                
                # Notification au membre
                Notification.objects.create(
                    destinataire=credit.membre,
                    expediteur=request.user,
                    type_notification='APPROBATION_CREDIT',
                    titre="Votre demande de crédit a été approuvée",
                    message=f"Montant accordé : {montant_accorde:,.0f} FBU",
                    lien=f"/credits/{credit.pk}/",
                )

                messages.success(
                    request,
                    f"✅ Crédit accordé avec succès ! "
                    f"Montant : {montant_accorde:,.2f} FBU | "
                    f"Fonds restants : {nouveaux_fonds:,.2f} FBU"
                )
            elif nouveau_statut == 'REJETE':
                # Notification au membre
                Notification.objects.create(
                    destinataire=credit.membre,
                    expediteur=request.user,
                    type_notification='REJET_CREDIT',
                    titre="Votre demande de crédit a été rejetée",
                    message=form.cleaned_data.get('remarque', '') or "Aucun motif fourni.",
                    lien=f"/credits/{credit.pk}/",
                )

                messages.warning(request, f"❌ Crédit rejeté.")
            
            return redirect('liste_credits')
    else:
        form = CreditApprovalForm(instance=credit, tenant=tenant)
    
    # Préparer le contexte avec toutes les informations
    context = {
        'form': form,
        'credit': credit,
        'total_cotisations': total_cotisations,
        'total_credits_accordes': total_credits_accordes,
        'fonds_disponibles': fonds_disponibles,
        'credits_en_cours': credits_en_cours,
        'peut_approuver': fonds_disponibles > 0,
        'montant_max_possible': fonds_disponibles,
    }
    
    return render(request, 'twiyungunganye/credits/approbation.html', context)


# INSTRUCTIONS POUR UTILISER CETTE VUE :
# 
# 1. Dans urls.py, remplacer :
#    path('credits/<int:pk>/approuver/', views.approuver_credit, name='approuver_credit'),
#    
#    Par :
#    path('credits/<int:pk>/approuver/', views.approuver_credit_strict, name='approuver_credit'),
#
# 2. Importer cette fonction dans views.py :
#    from .views_additions import approuver_credit_strict
#
# 3. Ou copier cette fonction directement dans views.py en remplacement de approuver_credit
