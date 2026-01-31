# Script pour créer des données de test
# À MODIFIER : Remplacez 'votre_projet' et 'votre_app' par vos vrais noms !

import os
import django

# MODIFIEZ CETTE LIGNE : Remplacez 'votre_projet' par le nom de votre projet Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'votre_projet.settings')
django.setup()

# MODIFIEZ CETTE LIGNE : Remplacez 'votre_app' par le nom de votre application Django
from votre_app.models import Association, Membre, Cotisation, CotisationImprevu, Credit
from django.utils import timezone
from decimal import Decimal

print("🔄 Création des données de test...")

# 1. Créer l'Association
association, created = Association.objects.get_or_create(
    id_association=1,
    defaults={
        'nom': 'Association Twiyungunganye',
        'sigle': 'ATG',
        'adresse': 'Gitega, Burundi',
        'telephone': '+257 22 00 00 00',
        'email': 'contact@twiyungunganye.bi',
        'montant_cotisation_mensuelle': Decimal('5000.00'),
        'montant_cotisation_imprevu_mensuelle': Decimal('2000.00'),
    }
)
print("✅ Association créée")

# 2. Créer des membres de test
membres_data = [
    {'nom': 'NDAYIZEYE', 'prenom': 'Jean', 'carte_identite': 'M001', 'telephone': '+257 79 00 00 01'},
    {'nom': 'NIYONKURU', 'prenom': 'Marie', 'carte_identite': 'M002', 'telephone': '+257 79 00 00 02'},
    {'nom': 'NKURUNZIZA', 'prenom': 'Pierre', 'carte_identite': 'M003', 'telephone': '+257 79 00 00 03'},
    {'nom': 'HAKIZIMANA', 'prenom': 'Grace', 'carte_identite': 'M004', 'telephone': '+257 79 00 00 04'},
    {'nom': 'BIZIMANA', 'prenom': 'Emmanuel', 'carte_identite': 'M005', 'telephone': '+257 79 00 00 05'},
]

membres = []
for data in membres_data:
    membre, created = Membre.objects.get_or_create(
        carte_identite=data['carte_identite'],
        defaults={
            'nom': data['nom'],
            'prenom': data['prenom'],
            'telephone': data['telephone'],
            'email': f"{data['prenom'].lower()}@exemple.com",
            'adresse': 'Gitega, Burundi',
        }
    )
    # Définir un mot de passe par défaut : "password123"
    if created:
        membre.set_password('password123')
        membre.save()
    membres.append(membre)
    print(f"✅ Membre créé : {membre.get_full_name()}")

# 3. Créer des cotisations régulières (6 mois pour chaque membre)
print("\n🔄 Création des cotisations régulières...")
cotisations_count = 0
for membre in membres:
    for mois in range(1, 7):  # Janvier à Juin 2025
        obj, created = Cotisation.objects.get_or_create(
            membre=membre,
            mois=mois,
            annee=2025,
            defaults={
                'montant': Decimal('5000.00'),
                'statut': 'PAYE',
                'date_paiement': timezone.now().date(),
            }
        )
        if created:
            cotisations_count += 1
print(f"✅ {cotisations_count} cotisations régulières créées")

# 4. Créer des cotisations imprévus (3 mois pour chaque membre)
print("\n🔄 Création des cotisations imprévus...")
imprevus_count = 0
for membre in membres:
    for mois in range(1, 4):  # Janvier à Mars 2025
        obj, created = CotisationImprevu.objects.get_or_create(
            membre=membre,
            mois=mois,
            annee=2025,
            defaults={
                'montant': Decimal('2000.00'),
                'statut': 'PAYE',
                'date_paiement': timezone.now().date(),
            }
        )
        if created:
            imprevus_count += 1
print(f"✅ {imprevus_count} cotisations imprévus créées")

# 5. Créer quelques crédits
print("\n🔄 Création des crédits...")
credits_data = [
    {
        'membre': membres[0], 
        'montant_demande': Decimal('50000.00'), 
        'montant_accorde': Decimal('50000.00'), 
        'statut': 'APPROUVE',
        'remarque': 'Crédit pour commerce'
    },
    {
        'membre': membres[1], 
        'montant_demande': Decimal('30000.00'), 
        'montant_accorde': Decimal('25000.00'), 
        'statut': 'APPROUVE',
        'remarque': 'Crédit pour éducation'
    },
    {
        'membre': membres[2], 
        'montant_demande': Decimal('20000.00'), 
        'montant_accorde': Decimal('0.00'), 
        'statut': 'EN_ATTENTE',
        'remarque': 'En attente de validation'
    },
]

credits_count = 0
for data in credits_data:
    obj, created = Credit.objects.get_or_create(
        membre=data['membre'],
        montant_demande=data['montant_demande'],
        defaults={
            'montant_accorde': data['montant_accorde'],
            'taux_interet': Decimal('5.00'),
            'statut': data['statut'],
            'date_demande': timezone.now().date(),
            'date_accord': timezone.now().date() if data['statut'] == 'APPROUVE' else None,
            'nombre_mois_ecoules': 2,
            'remarque': data['remarque'],
        }
    )
    if created:
        credits_count += 1
print(f"✅ {credits_count} crédits créés")

print("\n" + "="*50)
print("🎉 DONNÉES DE TEST CRÉÉES AVEC SUCCÈS !")
print("="*50)
print("\n📊 RÉSUMÉ :")
print(f"   - Association : 1")
print(f"   - Membres : {len(membres)}")
print(f"   - Cotisations régulières : {cotisations_count}")
print(f"   - Cotisations imprévus : {imprevus_count}")
print(f"   - Crédits : {credits_count}")
print("\n🔑 IDENTIFIANTS DE CONNEXION :")
print("   - Carte d'identité : M001, M002, M003, M004, ou M005")
print("   - Mot de passe : password123")
print("\n   - Admin : 123456789")
print("   - Mot de passe : (celui que vous avez défini)")
print("="*50)
print("\n💡 PROCHAINES ÉTAPES :")
print("   1. Lancez le serveur : python manage.py runserver")
print("   2. Ouvrez http://127.0.0.1:8000/admin")
print("   3. Connectez-vous et explorez les données !")
print("="*50)
