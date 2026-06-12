"""
Script pour créer des données de test pour l'application de cotisation

Utilisation:
    python generate_test_data.py
"""

import os
import django
import sys

# Configuration de Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cotisation.settings')
django.setup()

from twiyungunganye.models import Membre, Association, Cotisation, Credit
from decimal import Decimal
from datetime import date, timedelta
import random


def create_association():
    """Créer l'association"""
    print("Création de l'association...")
    
    association, created = Association.objects.get_or_create(
        nom="Association des Travailleurs Solidaires",
        defaults={
            'sigle': 'ATS',
            'adresse': 'Avenue de la Liberté, Bujumbura, Burundi',
            'telephone': '+257 22 XX XX XX',
            'email': 'contact@ats-burundi.bi',
            'montant_cotisation_mensuelle': Decimal('10000.00'),
        }
    )
    
    if created:
        print("✓ Association créée avec succès!")
    else:
        print("✓ Association déjà existante")
    
    return association


def create_membres():
    """Créer des membres de test"""
    print("\nCréation des membres...")
    
    membres_data = [
        {'nom': 'Nkurunziza', 'prenom': 'Pierre', 'carte_identite': '1234567890', 'email': 'pierre.nkurunziza@email.bi', 'telephone': '+257 79 XX XX 01'},
        {'nom': 'Ndayisenga', 'prenom': 'Marie', 'carte_identite': '2345678901', 'email': 'marie.ndayisenga@email.bi', 'telephone': '+257 79 XX XX 02'},
        {'nom': 'Bizimana', 'prenom': 'Jean', 'carte_identite': '3456789012', 'email': 'jean.bizimana@email.bi', 'telephone': '+257 79 XX XX 03'},
        {'nom': 'Uwimana', 'prenom': 'Claudine', 'carte_identite': '4567890123', 'email': 'claudine.uwimana@email.bi', 'telephone': '+257 79 XX XX 04'},
        {'nom': 'Hakizimana', 'prenom': 'Emmanuel', 'carte_identite': '5678901234', 'email': 'emmanuel.hakizimana@email.bi', 'telephone': '+257 79 XX XX 05'},
        {'nom': 'Nibigira', 'prenom': 'Ange', 'carte_identite': '6789012345', 'email': 'ange.nibigira@email.bi', 'telephone': '+257 79 XX XX 06'},
        {'nom': 'Niyonkuru', 'prenom': 'Fabrice', 'carte_identite': '7890123456', 'email': 'fabrice.niyonkuru@email.bi', 'telephone': '+257 79 XX XX 07'},
        {'nom': 'Kaneza', 'prenom': 'Grace', 'carte_identite': '8901234567', 'email': 'grace.kaneza@email.bi', 'telephone': '+257 79 XX XX 08'},
        {'nom': 'Sindayigaya', 'prenom': 'David', 'carte_identite': '9012345678', 'email': 'david.sindayigaya@email.bi', 'telephone': '+257 79 XX XX 09'},
        {'nom': 'Irakoze', 'prenom': 'Esperance', 'carte_identite': '0123456789', 'email': 'esperance.irakoze@email.bi', 'telephone': '+257 79 XX XX 10'},
    ]
    
    membres_crees = []
    for data in membres_data:
        membre, created = Membre.objects.get_or_create(
            carte_identite=data['carte_identite'],
            defaults={
                'nom': data['nom'],
                'prenom': data['prenom'],
                'email': data['email'],
                'telephone': data['telephone'],
                'adresse': 'Bujumbura, Burundi',
                'est_actif': True,
            }
        )
        
        if created:
            # Définir un mot de passe par défaut: "password123"
            membre.set_password('password123')
            membre.save()
            print(f"✓ Membre créé: {membre.get_full_name()} (Carte: {data['carte_identite']}, MDP: password123)")
        else:
            print(f"✓ Membre existant: {membre.get_full_name()}")
        
        membres_crees.append(membre)
    
    # Créer un gestionnaire
    gestionnaire, created = Membre.objects.get_or_create(
        carte_identite='GEST001',
        defaults={
            'nom': 'Gestionnaire',
            'prenom': 'Test',
            'email': 'gestionnaire@ats.bi',
            'telephone': '+257 79 XX XX 99',
            'adresse': 'Bujumbura, Burundi',
            'est_actif': True,
            'is_admin': True,
            'is_staff': True,
        }
    )
    
    if created:
        gestionnaire.set_password('gest123')
        gestionnaire.save()
        print(f"✓ Gestionnaire créé: {gestionnaire.get_full_name()} (Carte: GEST001, MDP: gest123)")
    
    return membres_crees


def create_cotisations(membres, association):
    """Créer des cotisations de test"""
    print("\nCréation des cotisations...")
    
    annee = 2025
    montant = association.montant_cotisation_mensuelle
    
    for mois in range(1, 13):  # Janvier à Décembre
        for membre in membres:
            # Créer des cotisations pour 80% des membres chaque mois
            if random.random() < 0.8:
                statut = random.choice(['PAYE', 'PAYE', 'PAYE', 'EN_ATTENTE'])
                
                cotisation, created = Cotisation.objects.get_or_create(
                    membre=membre,
                    mois=mois,
                    annee=annee,
                    defaults={
                        'montant': montant,
                        'statut': statut,
                        'date_paiement': date(annee, mois, random.randint(1, 28)),
                    }
                )
                
                if created:
                    print(f"  ✓ Cotisation créée: {membre.prenom} {membre.nom} - Mois {mois}")


def create_credits(membres):
    """Créer des crédits de test"""
    print("\nCréation des crédits...")
    
    montants_possibles = [50000, 100000, 150000, 200000, 250000, 300000]
    
    # Créer 5 crédits aléatoires
    for i in range(5):
        membre = random.choice(membres)
        montant = random.choice(montants_possibles)
        
        credit, created = Credit.objects.get_or_create(
            membre=membre,
            montant_demande=Decimal(montant),
            defaults={
                'montant_accorde': Decimal(montant),
                'taux_interet': Decimal('5.00'),
                'statut': random.choice(['APPROUVE', 'EN_COURS']),
                'date_demande': date(2025, random.randint(1, 6), random.randint(1, 28)),
                'date_accord': date(2025, random.randint(1, 6), random.randint(1, 28)),
                'nombre_mois_ecoules': random.randint(1, 6),
                'remarque': 'Crédit de test pour développement',
            }
        )
        
        if created:
            print(f"  ✓ Crédit créé: {membre.get_full_name()} - {montant} FC")


def main():
    """Fonction principale"""
    print("=" * 60)
    print("GÉNÉRATION DES DONNÉES DE TEST")
    print("=" * 60)
    
    try:
        # Créer l'association
        association = create_association()
        
        # Créer les membres
        membres = create_membres()
        
        # Créer les cotisations
        create_cotisations(membres, association)
        
        # Créer les crédits
        create_credits(membres)
        
        print("\n" + "=" * 60)
        print("✓ DONNÉES DE TEST CRÉÉES AVEC SUCCÈS!")
        print("=" * 60)
        print("\nComptes de test créés:")
        print("-" * 60)
        print("Membres: 10 comptes (MDP: password123)")
        print("  Exemple: Carte ID: 1234567890, MDP: password123")
        print("\nGestionnaire:")
        print("  Carte ID: GEST001, MDP: gest123")
        print("\nSuperutilisateur (à créer):")
        print("  Exécutez: python manage.py createsuperuser")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
