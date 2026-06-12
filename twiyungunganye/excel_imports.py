import openpyxl
from django.contrib import messages
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Membre
from .excel_exports import get_tenant, is_admin_or_gestionnaire

@login_required
@user_passes_test(is_admin_or_gestionnaire)
def import_membres_excel(request):
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        
        # Validation d'extension
        if not excel_file.name.endswith('.xlsx'):
            messages.error(request, "Veuillez fournir un fichier au format .xlsx")
            return redirect('liste_membres')

        try:
            wb = openpyxl.load_workbook(excel_file)
            ws = wb.active
            tenant = get_tenant(request)

            membres_crees = 0
            membres_ignores = 0

            # On part de la 2ème ligne pour ignorer les en-têtes
            for row in ws.iter_rows(min_row=2, values_only=True):
                if not row or not row[1]:  # Si la ligne est vide ou pas de nom (en supposant le nom à l'index 1)
                    continue

                nom = str(row[1]).strip() if len(row) > 1 and row[1] else ''
                prenom = str(row[2]).strip() if len(row) > 2 and row[2] else ''
                carte_identite = str(row[3]).strip() if len(row) > 3 and row[3] else ''
                email = str(row[4]).strip() if len(row) > 4 and row[4] else None
                telephone = str(row[5]).strip() if len(row) > 5 and row[5] else None
                adresse = str(row[6]).strip() if len(row) > 6 and row[6] else None

                if not nom or not prenom or not carte_identite:
                    membres_ignores += 1
                    continue

                # Vérifier si la carte d'identité existe déjà globalement
                if Membre.objects.filter(carte_identite=carte_identite).exists():
                    membres_ignores += 1
                    continue

                # Créer le membre
                Membre.objects.create(
                    tenant=tenant,
                    nom=nom,
                    prenom=prenom,
                    carte_identite=carte_identite,
                    email=email if email != 'None' else None,
                    telephone=telephone if telephone != 'None' else None,
                    adresse=adresse if adresse != 'None' else None,
                    est_actif=True
                )
                membres_crees += 1

            messages.success(request, f"Importation réussie : {membres_crees} membres ajoutés, {membres_ignores} ignorés (doublons ou incomplets).")
        except Exception as e:
            messages.error(request, f"Erreur lors de l'importation : {str(e)}")
            
    return redirect('liste_membres')
