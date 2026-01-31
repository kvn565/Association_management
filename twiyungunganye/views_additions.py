"""
Fichier : views_additions.py
Description : Fonctions supplémentaires à ajouter dans views.py
Ces fonctions remplacent ou complètent les vues existantes
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from decimal import Decimal

from .models import Credit, Association
from .forms import CreditApprovalForm


def is_admin_only(user):
    return user.is_authenticated and user.is_admin


@login_required
@user_passes_test(is_admin_only)
def approuver_credit_strict(request, pk):
    """
    Approuver ou rejeter un crédit avec VALIDATION STRICTE des fonds
    
    LOGIQUE :
    1. Calculer le total des cotisations payées
    2. Calculer le total des crédits déjà accordés et non remboursés
    3. Fonds disponibles = Cotisations - Crédits en cours
    4. BLOQUER si montant demandé > fonds disponibles
    """
    credit = get_object_or_404(Credit, pk=pk)
    association = Association.get_association()
    
    if not association:
        messages.error(request, "⚠️ Erreur : Association non configurée.")
        return redirect('liste_credits')
    
    # ÉTAPE 1 : Calculer le total des cotisations
    total_cotisations = association.get_total_cotisations_disponibles()
    
    # ÉTAPE 2 : Calculer le total des crédits en cours (sauf celui qu'on traite)
    credits_en_cours = Credit.objects.filter(
        statut__in=['APPROUVE', 'EN_COURS']
    ).exclude(pk=credit.pk)
    
    total_credits_accordes = Decimal('0')
    for c in credits_en_cours:
        total_credits_accordes += c.montant_accorde
    
    # ÉTAPE 3 : Calculer les fonds disponibles
    fonds_disponibles = total_cotisations - total_credits_accordes
    
    if request.method == 'POST':
        form = CreditApprovalForm(request.POST, instance=credit)
        
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
                    f"Total cotisations = {total_cotisations:,.2f} FBU | "
                    f"Crédits en cours = {total_credits_accordes:,.2f} FBU"
                )
                
                return redirect('approuver_credit', pk=credit.pk)
            
            # Si validation OK ou si c'est un rejet, sauvegarder
            form.save()
            
            if nouveau_statut == 'APPROUVE':
                # Calculer les nouveaux fonds restants
                nouveaux_fonds = fonds_disponibles - montant_accorde
                
                messages.success(
                    request,
                    f"✅ Crédit accordé avec succès ! "
                    f"Montant : {montant_accorde:,.2f} FBU | "
                    f"Fonds restants : {nouveaux_fonds:,.2f} FBU"
                )
            elif nouveau_statut == 'REJETE':
                messages.warning(request, f"❌ Crédit rejeté.")
            
            return redirect('liste_credits')
    else:
        form = CreditApprovalForm(instance=credit)
    
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
