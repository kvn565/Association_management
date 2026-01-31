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
                # Supprimer toutes les données dans l'ordre correct
                
                # 1. Supprimer les remboursements
                count_remb = Remboursement.objects.count()
                Remboursement.objects.all().delete()
                
                # 2. Supprimer les intérêts
                count_int = Interet.objects.count()
                Interet.objects.all().delete()
                
                # 3. Supprimer les crédits
                count_cred = Credit.objects.count()
                Credit.objects.all().delete()
                
                # 4. Supprimer les cotisations
                count_cot = Cotisation.objects.count()
                Cotisation.objects.all().delete()
                
                # 5. Supprimer les suggestions
                count_sug = Suggestion.objects.count()
                Suggestion.objects.all().delete()
                
                # 6. Supprimer les membres (sauf superadmin)
                count_memb = Membre.objects.filter(is_superuser=False).count()
                Membre.objects.filter(is_superuser=False).delete()
                
                # 7. Réinitialiser les séquences auto-increment (SQLite)
                try:
                    with connection.cursor() as cursor:
                        cursor.execute("DELETE FROM sqlite_sequence WHERE name='cotisations'")
                        cursor.execute("DELETE FROM sqlite_sequence WHERE name='credits'")
                        cursor.execute("DELETE FROM sqlite_sequence WHERE name='remboursements'")
                        cursor.execute("DELETE FROM sqlite_sequence WHERE name='interets'")
                        cursor.execute("DELETE FROM sqlite_sequence WHERE name='suggestions'")
                        cursor.execute("DELETE FROM sqlite_sequence WHERE name='membres'")
                except:
                    pass  # Si ce n'est pas SQLite, ignorer
                
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
    stats = {
        'membres': Membre.objects.filter(is_superuser=False).count(),
        'cotisations': Cotisation.objects.count(),
        'credits': Credit.objects.count(),
        'remboursements': Remboursement.objects.count(),
        'suggestions': Suggestion.objects.count(),
        'interets': Interet.objects.count(),
    }
    
    context = {
        'stats': stats,
    }
    
    return render(request, 'twiyungunganye/reinitialiser_base_donnees.html', context)
