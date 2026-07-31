"""
Fichier : admin_views.py
Description : Vues administratives pour validation stricte et réinitialisation
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db import connection
from django.http import HttpResponse
from decimal import Decimal
from datetime import datetime

from .models import (
    Membre, Cotisation, CotisationImprevu, Credit, Interet,
    Remboursement, Association, Suggestion, PenaliteCotisation
)
from cas_assistance.models import CasAssistance
from .excel_exports import generer_backup_tenant


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
                
                # GÉNÉRER LE BACKUP EXCEL AVANT SUPPRESSION
                buffer, nom_tenant, now = generer_backup_tenant(tenant, request)
                
                # SUPPRESSION DE TOUTES LES DONNÉES
                count_remb = tenant_qs(Remboursement.objects.all()).count()
                tenant_qs(Remboursement.objects.all()).delete()
                count_int = tenant_qs(Interet.objects.all()).count()
                tenant_qs(Interet.objects.all()).delete()
                count_pen = tenant_qs(PenaliteCotisation.objects.all()).count()
                tenant_qs(PenaliteCotisation.objects.all()).delete()
                count_cred = tenant_qs(Credit.objects.all()).count()
                tenant_qs(Credit.objects.all()).delete()
                count_cot = tenant_qs(Cotisation.objects.all()).count()
                tenant_qs(Cotisation.objects.all()).delete()
                count_imp = tenant_qs(CotisationImprevu.objects.all()).count()
                tenant_qs(CotisationImprevu.objects.all()).delete()
                count_assist = tenant_qs(CasAssistance.objects.all()).count()
                tenant_qs(CasAssistance.objects.all()).delete()
                count_sug = tenant_qs(Suggestion.objects.all()).count()
                tenant_qs(Suggestion.objects.all()).delete()
                membres = Membre.objects.filter(is_superuser=False).exclude(pk=request.user.pk)
                if tenant:
                    membres = membres.filter(tenant=tenant)
                count_memb = membres.count()
                membres.delete()
                
                # Retourner le fichier Excel
                response = HttpResponse(buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                response['Content-Disposition'] = f'attachment; filename="Backup_{nom_tenant}_{now}.xlsx"'
                return response
                
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
        imprevus_qs = CotisationImprevu.objects.filter(tenant=tenant)
        credits_qs = Credit.objects.filter(tenant=tenant)
        remboursements_qs = Remboursement.objects.filter(tenant=tenant)
        suggestions_qs = Suggestion.objects.filter(tenant=tenant)
        interets_qs = Interet.objects.filter(tenant=tenant)
        penalites_qs = PenaliteCotisation.objects.filter(tenant=tenant)
        assistances_qs = CasAssistance.objects.filter(tenant=tenant)
    else:
        cotisations_qs = Cotisation.objects.all()
        imprevus_qs = CotisationImprevu.objects.all()
        credits_qs = Credit.objects.all()
        remboursements_qs = Remboursement.objects.all()
        suggestions_qs = Suggestion.objects.all()
        interets_qs = Interet.objects.all()
        penalites_qs = PenaliteCotisation.objects.all()
        assistances_qs = CasAssistance.objects.all()
    
    stats = {
        'membres': membres_qs.count(),
        'cotisations': cotisations_qs.count(),
        'imprevus': imprevus_qs.count(),
        'credits': credits_qs.count(),
        'remboursements': remboursements_qs.count(),
        'suggestions': suggestions_qs.count(),
        'interets': interets_qs.count(),
        'penalites': penalites_qs.count(),
        'assistances': assistances_qs.count(),
    }
    
    context = {
        'stats': stats,
    }
    
    return render(request, 'twiyungunganye/reinitialiser_base_donnees.html', context)
