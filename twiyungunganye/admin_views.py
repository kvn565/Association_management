"""
Fichier : admin_views.py
Description : Vues administratives pour validation stricte et réinitialisation
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db import connection
from decimal import Decimal

from .models import (
    Membre, Cotisation, Credit, Interet,
    Remboursement, Association, Suggestion
)


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
def reinitialiser_base_donnees(request):
    """
    Réinitialiser complètement la base de données
    ATTENTION : Cette action est IRRÉVERSIBLE !
    """
    if request.method == 'POST':
        # Vérifier le code de confirmation
        confirmation = request.POST.get('confirmation', '')
        
        if confirmation == 'REINITIALISER':
            try:
                tenant = get_tenant(request)
                
                def tenant_qs(qs):
                    if tenant:
                        return qs.filter(tenant=tenant)
                    return qs
                
                # Supprimer toutes les données dans l'ordre correct
                
                # 1. Supprimer les remboursements
                count_remb = tenant_qs(Remboursement.objects.all()).count()
                tenant_qs(Remboursement.objects.all()).delete()
                
                # 2. Supprimer les intérêts
                count_int = tenant_qs(Interet.objects.all()).count()
                tenant_qs(Interet.objects.all()).delete()
                
                # 3. Supprimer les crédits
                count_cred = tenant_qs(Credit.objects.all()).count()
                tenant_qs(Credit.objects.all()).delete()
                
                # 4. Supprimer les cotisations
                count_cot = tenant_qs(Cotisation.objects.all()).count()
                tenant_qs(Cotisation.objects.all()).delete()
                
                # 5. Supprimer les suggestions
                count_sug = tenant_qs(Suggestion.objects.all()).count()
                tenant_qs(Suggestion.objects.all()).delete()
                
                # 6. Supprimer les membres (sauf superadmin et l'utilisateur courant)
                membres = Membre.objects.filter(is_superuser=False).exclude(pk=request.user.pk)
                if tenant:
                    membres = membres.filter(tenant=tenant)
                count_memb = membres.count()
                membres.delete()
                
                messages.success(
                    request,
                    f"✅ Base de données réinitialisée avec succès ! "
                    f"Données supprimées : {count_memb} membres, {count_cot} cotisations, "
                    f"{count_cred} crédits, {count_remb} remboursements, {count_sug} suggestions."
                )
                
                return redirect('dashboard')
                
            except Exception as e:
                messages.error(
                    request,
                    f"❌ Erreur lors de la réinitialisation : {str(e)}"
                )
                return redirect('reinitialiser_base_donnees')
        else:
            messages.error(
                request,
                "❌ Code de confirmation incorrect. Veuillez taper exactement 'REINITIALISER' (en majuscules)"
            )
    
    # Afficher les statistiques actuelles
    tenant = get_tenant(request)
    membres_qs = Membre.objects.filter(is_superuser=False)
    if tenant:
        membres_qs = membres_qs.filter(tenant=tenant)
        cotisations_qs = Cotisation.objects.filter(tenant=tenant)
        credits_qs = Credit.objects.filter(tenant=tenant)
        remboursements_qs = Remboursement.objects.filter(tenant=tenant)
        suggestions_qs = Suggestion.objects.filter(tenant=tenant)
        interets_qs = Interet.objects.filter(tenant=tenant)
    else:
        cotisations_qs = Cotisation.objects.all()
        credits_qs = Credit.objects.all()
        remboursements_qs = Remboursement.objects.all()
        suggestions_qs = Suggestion.objects.all()
        interets_qs = Interet.objects.all()
    
    stats = {
        'membres': membres_qs.count(),
        'cotisations': cotisations_qs.count(),
        'credits': credits_qs.count(),
        'remboursements': remboursements_qs.count(),
        'suggestions': suggestions_qs.count(),
        'interets': interets_qs.count(),
    }
    
    context = {
        'stats': stats,
    }
    
    return render(request, 'twiyungunganye/reinitialiser_base_donnees.html', context)
