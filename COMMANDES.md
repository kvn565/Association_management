# COMMANDES ESSENTIELLES - APPLICATION COTISATION

## INSTALLATION INITIALE

### 1. Naviguer vers le dossier du projet
```cmd
cd C:\Users\MSC KEVIN\Desktop\projectsdjango\cotisation
```

### 2. Installer les dépendances
```cmd
pip install -r requirements.txt
```

### 3. Créer et appliquer les migrations
```cmd
python manage.py makemigrations
python manage.py migrate
```

### 4. Créer un superutilisateur (administrateur)
```cmd
python manage.py createsuperuser
```
Vous devrez entrer:
- Carte d'identité (ex: ADMIN001)
- Nom
- Prénom
- Mot de passe (2 fois)

### 5. Générer des données de test (optionnel)
```cmd
python generate_test_data.py
```

### 6. Lancer le serveur
```cmd
python manage.py runserver
```

---

## COMMANDES QUOTIDIENNES

### Lancer le serveur
```cmd
python manage.py runserver
```

### Arrêter le serveur
Appuyez sur `Ctrl + C` dans le terminal

---

## GESTION DE LA BASE DE DONNÉES

### Créer des migrations après modification des modèles
```cmd
python manage.py makemigrations
```

### Appliquer les migrations
```cmd
python manage.py migrate
```

### Réinitialiser la base de données (ATTENTION: supprime toutes les données!)
```cmd
del db.sqlite3
python manage.py migrate
python manage.py createsuperuser
python generate_test_data.py
```

### Exporter les données
```cmd
python manage.py dumpdata > backup.json
```

### Importer les données
```cmd
python manage.py loaddata backup.json
```

---

## GESTION DES UTILISATEURS

### Créer un superutilisateur
```cmd
python manage.py createsuperuser
```

### Changer le mot de passe d'un utilisateur
```cmd
python manage.py changepassword CARTE_IDENTITE
```

### Créer un shell interactif Django
```cmd
python manage.py shell
```
Puis dans le shell:
```python
from twiyungunganye.models import Membre
membre = Membre.objects.get(carte_identite='1234567890')
membre.set_password('nouveau_mot_de_passe')
membre.save()
```

---

## URLS DE L'APPLICATION

### Interface publique
```
http://127.0.0.1:8000/
```

### Interface d'administration Django
```
http://127.0.0.1:8000/admin/
```

### Connexion membre
```
http://127.0.0.1:8000/login/
```

### Création de mot de passe (première connexion)
```
http://127.0.0.1:8000/creer-mot-de-passe/
```

### Dashboard
```
http://127.0.0.1:8000/dashboard/
```

### Liste des membres
```
http://127.0.0.1:8000/membres/
```

### Liste des cotisations
```
http://127.0.0.1:8000/cotisations/
```

### Liste des crédits
```
http://127.0.0.1:8000/credits/
```

### Demander un crédit
```
http://127.0.0.1:8000/credits/demander/
```

### Rapports
```
http://127.0.0.1:8000/rapports/
```

---

## COMMANDES DE DÉBOGAGE

### Vérifier la configuration
```cmd
python manage.py check
```

### Afficher les migrations
```cmd
python manage.py showmigrations
```

### Lancer les tests
```cmd
python manage.py test
```

### Créer un shell Python avec Django
```cmd
python manage.py shell
```

### Collecter les fichiers statiques
```cmd
python manage.py collectstatic
```

---

## CODES D'ERREUR COURANTS ET SOLUTIONS

### Erreur: "No module named 'reportlab'"
**Solution:**
```cmd
pip install reportlab
```

### Erreur: "No module named 'PIL'"
**Solution:**
```cmd
pip install Pillow
```

### Erreur: "OperationalError: no such table"
**Solution:**
```cmd
python manage.py migrate
```

### Erreur: "ImportError: cannot import name 'Membre'"
**Solution:**
Vérifiez que le fichier models.py est bien mis à jour et relancez:
```cmd
python manage.py makemigrations
python manage.py migrate
```

### Erreur: Port 8000 déjà utilisé
**Solution:**
Utilisez un autre port:
```cmd
python manage.py runserver 8080
```

---

## COMPTES DE TEST (après generate_test_data.py)

### Membres
- Carte ID: 1234567890, MDP: password123
- Carte ID: 2345678901, MDP: password123
- Carte ID: 3456789012, MDP: password123
- (etc... 10 membres au total)

### Gestionnaire
- Carte ID: GEST001, MDP: gest123

### Superutilisateur
À créer avec: `python manage.py createsuperuser`

---

## MAINTENANCE

### Sauvegarder la base de données
```cmd
copy db.sqlite3 db_backup_%date:~-4,4%%date:~-7,2%%date:~-10,2%.sqlite3
```

### Vérifier l'espace disque
```cmd
dir
```

### Nettoyer les fichiers temporaires Python
```cmd
python manage.py clean_pyc
```

---

## PRODUCTION (déploiement)

### Collecter les fichiers statiques
```cmd
python manage.py collectstatic --noinput
```

### Variables d'environnement à configurer
- `SECRET_KEY`: Nouvelle clé secrète
- `DEBUG`: False
- `ALLOWED_HOSTS`: Votre domaine
- `DATABASE_URL`: URL de votre base de données

### Commandes de déploiement
```cmd
python manage.py migrate
python manage.py collectstatic
python manage.py createsuperuser
```

---

## SUPPORT

Pour plus d'informations, consultez:
- README.md
- GUIDE_INSTALLATION.md
- Documentation Django: https://docs.djangoproject.com/
