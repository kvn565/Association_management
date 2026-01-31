# GUIDE D'INSTALLATION WINDOWS - Avec Données de Test

## 🪟 Guide spécifique pour Windows avec SQLite

---

## ÉTAPE 1 : PRÉPARATION

### 1.1 Ouvrir l'invite de commandes (CMD)

```cmd
# Appuyez sur : Windows + R
# Tapez : cmd
# Appuyez sur Entrée
```

### 1.2 Aller dans votre dossier de projet

```cmd
cd C:\chemin\vers\votre\projet
```

**Exemple :**
```cmd
cd C:\Users\VotreNom\Documents\mon_projet_django
```

### 1.3 Vérifier que vous êtes au bon endroit

```cmd
dir

# Vous devriez voir :
# - manage.py
# - db.sqlite3
# - votre_app (dossier)
```

---

## ÉTAPE 2 : SAUVEGARDE RAPIDE (Optionnel mais recommandé)

### 2.1 Créer un dossier de sauvegarde

```cmd
mkdir backups
```

### 2.2 Copier la base de données actuelle

```cmd
copy db.sqlite3 backups\db.sqlite3.backup
```

### 2.3 Copier les anciens fichiers Python

```cmd
copy votre_app\models.py backups\models.py.backup
copy votre_app\forms.py backups\forms.py.backup
copy votre_app\views.py backups\views.py.backup
copy votre_app\admin.py backups\admin.py.backup
```

---

## ÉTAPE 3 : SUPPRIMER L'ANCIENNE BASE DE DONNÉES

**⚠️ Comme vous n'avez pas de données importantes, on va repartir à zéro !**

```cmd
# Supprimer l'ancienne base de données
del db.sqlite3

# Supprimer toutes les anciennes migrations (SAUF __init__.py)
del votre_app\migrations\0*.py
```

**Note :** Gardez uniquement le fichier `__init__.py` dans le dossier migrations !

---

## ÉTAPE 4 : REMPLACER LES FICHIERS

### 4.1 Copier les nouveaux fichiers

**Remplacez "C:\Téléchargements" par le dossier où vous avez téléchargé les nouveaux fichiers**

```cmd
# Copier models.py
copy "C:\Téléchargements\models.py" votre_app\models.py

# Copier forms.py
copy "C:\Téléchargements\forms.py" votre_app\forms.py

# Copier views.py
copy "C:\Téléchargements\views.py" votre_app\views.py

# Copier admin.py
copy "C:\Téléchargements\admin.py" votre_app\admin.py
```

### 4.2 Vérifier que les fichiers sont bien copiés

```cmd
dir votre_app\models.py
dir votre_app\forms.py
dir votre_app\views.py
dir votre_app\admin.py

# Chaque fichier devrait afficher sa taille (plusieurs Ko)
```

---

## ÉTAPE 5 : CRÉER LES NOUVELLES MIGRATIONS

### 5.1 Créer les migrations

```cmd
python manage.py makemigrations
```

**Vous devriez voir :**
```
Migrations for 'votre_app':
  votre_app\migrations\0001_initial.py
    - Create model Association
    - Create model Membre
    - Create model Cotisation
    - Create model CotisationImprevu
    - Create model Credit
    - Create model Interet
    - Create model Remboursement
    - Create model Suggestion
```

### 5.2 Appliquer les migrations

```cmd
python manage.py migrate
```

**Vous devriez voir :**
```
Running migrations:
  Applying contenttypes.0001_initial... OK
  Applying contenttypes.0002_remove_content_type_name... OK
  Applying auth.0001_initial... OK
  ...
  Applying votre_app.0001_initial... OK
```

---

## ÉTAPE 6 : CRÉER UN SUPER UTILISATEUR

```cmd
python manage.py createsuperuser
```

**Remplissez les informations :**
```
Carte d'identité: 123456789
Nom: Admin
Prénom: Super
Email: admin@exemple.com
Password: ******** (votre mot de passe)
Password (again): ******** (confirmez)
```

---

## ÉTAPE 7 : CHARGER LES DONNÉES DE TEST

### 7.1 Créer le fichier de données de test

**Créez un fichier `data_test.py` dans le dossier de votre projet :**

```cmd
notepad data_test.py
```

**Collez ce code dans le fichier :**

```python
# Script pour créer des données de test
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'votre_projet.settings')
django.setup()

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
for membre in membres:
    for mois in range(1, 7):  # Janvier à Juin 2025
        Cotisation.objects.get_or_create(
            membre=membre,
            mois=mois,
            annee=2025,
            defaults={
                'montant': Decimal('5000.00'),
                'statut': 'PAYE',
                'date_paiement': timezone.now().date(),
            }
        )
print(f"✅ {len(membres) * 6} cotisations régulières créées")

# 4. Créer des cotisations imprévus (3 mois pour chaque membre)
print("\n🔄 Création des cotisations imprévus...")
for membre in membres:
    for mois in range(1, 4):  # Janvier à Mars 2025
        CotisationImprevu.objects.get_or_create(
            membre=membre,
            mois=mois,
            annee=2025,
            defaults={
                'montant': Decimal('2000.00'),
                'statut': 'PAYE',
                'date_paiement': timezone.now().date(),
            }
        )
print(f"✅ {len(membres) * 3} cotisations imprévus créées")

# 5. Créer quelques crédits
print("\n🔄 Création des crédits...")
credits_data = [
    {'membre': membres[0], 'montant_demande': Decimal('50000.00'), 'montant_accorde': Decimal('50000.00'), 'statut': 'APPROUVE'},
    {'membre': membres[1], 'montant_demande': Decimal('30000.00'), 'montant_accorde': Decimal('25000.00'), 'statut': 'APPROUVE'},
    {'membre': membres[2], 'montant_demande': Decimal('20000.00'), 'montant_accorde': Decimal('0.00'), 'statut': 'EN_ATTENTE'},
]

for data in credits_data:
    Credit.objects.get_or_create(
        membre=data['membre'],
        montant_demande=data['montant_demande'],
        defaults={
            'montant_accorde': data['montant_accorde'],
            'taux_interet': Decimal('5.00'),
            'statut': data['statut'],
            'date_demande': timezone.now().date(),
            'date_accord': timezone.now().date() if data['statut'] == 'APPROUVE' else None,
            'nombre_mois_ecoules': 2,
        }
    )
print(f"✅ {len(credits_data)} crédits créés")

print("\n" + "="*50)
print("🎉 DONNÉES DE TEST CRÉÉES AVEC SUCCÈS !")
print("="*50)
print("\n📊 RÉSUMÉ :")
print(f"   - Association : 1")
print(f"   - Membres : {len(membres)}")
print(f"   - Cotisations régulières : {len(membres) * 6}")
print(f"   - Cotisations imprévus : {len(membres) * 3}")
print(f"   - Crédits : {len(credits_data)}")
print("\n🔑 IDENTIFIANTS DE CONNEXION :")
print("   - Carte d'identité : M001, M002, M003, M004, ou M005")
print("   - Mot de passe : password123")
print("\n   - Admin : 123456789")
print("   - Mot de passe : (celui que vous avez défini)")
print("="*50)
```

**Sauvegardez le fichier** (Ctrl+S puis fermez Notepad)

### 7.2 Modifier le script pour votre projet

**IMPORTANT : Modifiez ces lignes dans le fichier `data_test.py` :**

```python
# Ligne 5 : Remplacez par le nom de votre projet
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'votre_projet.settings')

# Ligne 8 : Remplacez par le nom de votre app
from votre_app.models import Association, Membre, Cotisation, CotisationImprevu, Credit
```

**Exemple concret :**
Si votre projet s'appelle `gestion_association` et votre app `cotisations` :
```python
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_association.settings')
from cotisations.models import Association, Membre, Cotisation, CotisationImprevu, Credit
```

### 7.3 Exécuter le script

```cmd
python data_test.py
```

**Vous devriez voir :**
```
🔄 Création des données de test...
✅ Association créée
✅ Membre créé : Jean NDAYIZEYE
✅ Membre créé : Marie NIYONKURU
...
🎉 DONNÉES DE TEST CRÉÉES AVEC SUCCÈS !
```

---

## ÉTAPE 8 : LANCER LE SERVEUR ET TESTER

### 8.1 Lancer le serveur

```cmd
python manage.py runserver
```

**Vous devriez voir :**
```
Starting development server at http://127.0.0.1:8000/
```

### 8.2 Ouvrir le navigateur

Ouvrez votre navigateur et allez sur : **http://127.0.0.1:8000/admin**

### 8.3 Se connecter

**Option 1 : Avec le super utilisateur**
- Carte d'identité : 123456789
- Mot de passe : (celui que vous avez créé)

**Option 2 : Avec un membre de test**
- Carte d'identité : M001 (ou M002, M003, M004, M005)
- Mot de passe : password123

---

## ÉTAPE 9 : VÉRIFICATIONS

### 9.1 Dans l'admin Django

✅ Vérifiez ces éléments dans l'admin :

1. **Association** : 
   - Cliquez sur "Associations"
   - Vous devriez voir "Association Twiyungunganye"
   - Montant cotisation mensuelle : 5000 FBU
   - Montant cotisation imprévus : 2000 FBU

2. **Membres** :
   - Cliquez sur "Membres"
   - Vous devriez voir 5 membres + votre super utilisateur

3. **Cotisations** :
   - Cliquez sur "Cotisations"
   - Vous devriez voir 30 cotisations (5 membres × 6 mois)
   - Tous les montants en FBU ✅

4. **Cotisations Imprévus** :
   - Cliquez sur "Cotisation Imprevus"
   - Vous devriez voir 15 cotisations (5 membres × 3 mois)
   - Tous les montants en FBU ✅

5. **Crédits** :
   - Cliquez sur "Crédits"
   - Vous devriez voir 3 crédits
   - Montants affichés en FBU ✅

### 9.2 Tester la validation des crédits

1. **Connectez-vous avec un membre sans cotisations** :
   - Créez un nouveau membre dans l'admin sans cotisations
   - Connectez-vous avec ce membre
   - Essayez de demander un crédit
   - ✅ Vous devriez voir un message d'erreur

2. **Avec un membre ayant des cotisations** :
   - Connectez-vous avec M001 (qui a 6 mois de cotisations)
   - Demandez un crédit
   - ✅ La demande devrait passer

---

## ÉTAPE 10 : CONFIGURATION FINALE

### 10.1 Donner les droits admin à un membre

Si vous voulez qu'un membre puisse accéder à l'interface admin :

1. Allez dans **Admin → Membres**
2. Cliquez sur un membre (ex: Jean NDAYIZEYE)
3. Cochez ces cases :
   - ✅ **Is admin** (pour droits complets)
   - OU ✅ **Is gestionnaire** (pour droits limités)
4. Sauvegardez

---

## 📝 COMMANDES RÉCAPITULATIVES (À copier-coller)

### Si vous devez tout refaire :

```cmd
# 1. Aller dans le projet
cd C:\chemin\vers\votre\projet

# 2. Supprimer l'ancienne base
del db.sqlite3
del votre_app\migrations\0*.py

# 3. Créer les nouvelles migrations
python manage.py makemigrations
python manage.py migrate

# 4. Créer le super utilisateur
python manage.py createsuperuser

# 5. Charger les données de test
python data_test.py

# 6. Lancer le serveur
python manage.py runserver
```

---

## 🎯 RÉSULTAT FINAL

Après avoir suivi ce guide, vous aurez :

✅ Une base de données SQLite toute neuve
✅ 5 membres de test avec cotisations
✅ Des cotisations régulières (30 entrées)
✅ Des cotisations imprévus (15 entrées)
✅ 3 crédits de démonstration
✅ Tous les montants en FBU
✅ Validation des crédits fonctionnelle

---

## 🔑 IDENTIFIANTS DE CONNEXION

### Super Admin :
- **Carte d'identité** : 123456789
- **Mot de passe** : (celui que vous avez défini)

### Membres de test :
- **Carte d'identité** : M001, M002, M003, M004, ou M005
- **Mot de passe** : password123

---

## 🚨 EN CAS DE PROBLÈME

### Erreur : "No module named 'votre_app'"
**Solution :** Vérifiez le nom de votre app dans `data_test.py`

### Erreur : "DJANGO_SETTINGS_MODULE"
**Solution :** Vérifiez le nom de votre projet dans `data_test.py` ligne 5

### Erreur : "Table already exists"
**Solution :** Supprimez `db.sqlite3` et recommencez à l'étape 3

### Le serveur ne démarre pas
**Solution :**
```cmd
# Vérifiez qu'il n'y a pas d'erreurs
python manage.py check

# Si erreur, lisez le message et corrigez
```

---

## 📞 PROCHAINES ÉTAPES

Maintenant que votre système fonctionne, vous pouvez :

1. **Personnaliser l'association** dans l'admin
2. **Ajouter vos vrais membres** (ou modifier les membres de test)
3. **Créer les templates** pour l'interface utilisateur
4. **Tester toutes les fonctionnalités**

---

**Félicitations ! Votre système est maintenant configuré avec FBU et les cotisations imprévus !** 🎉
