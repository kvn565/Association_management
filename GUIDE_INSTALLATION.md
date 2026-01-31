# GUIDE D'INSTALLATION DES FICHIERS

Ce document explique comment installer tous les fichiers de votre application Django.

## Structure des fichiers à créer/remplacer

```
C:\Users\MSC KEVIN\Desktop\projectsdjango\cotisation\
│
├── cotisation/                          # Dossier de configuration du projet
│   ├── __init__.py                     # (déjà existant - ne pas modifier)
│   ├── settings.py                     # ⚠️ À REMPLACER avec settings_updated.py
│   ├── urls.py                         # ⚠️ À REMPLACER avec urls_projet.py
│   ├── asgi.py                         # (déjà existant - ne pas modifier)
│   └── wsgi.py                         # (déjà existant - ne pas modifier)
│
├── twiyungunganye/                      # Dossier de l'application
│   ├── __init__.py                     # (déjà existant - ne pas modifier)
│   ├── admin.py                        # ⚠️ À REMPLACER avec admin.py
│   ├── apps.py                         # (déjà existant - ne pas modifier)
│   ├── models.py                       # ⚠️ À REMPLACER avec models.py
│   ├── views.py                        # ⚠️ À REMPLACER avec views.py
│   ├── forms.py                        # ✅ NOUVEAU FICHIER - À CRÉER
│   ├── urls.py                         # ✅ NOUVEAU FICHIER - À CRÉER (urls_app.py)
│   ├── pdf_reports.py                  # ✅ NOUVEAU FICHIER - À CRÉER
│   └── tests.py                        # (déjà existant - peut rester tel quel)
│
├── static/                              # ✅ NOUVEAU DOSSIER - À CRÉER
│   └── (fichiers CSS, JS, images)
│
├── media/                               # ✅ NOUVEAU DOSSIER - À CRÉER
│   └── logos/                          # ✅ SOUS-DOSSIER - À CRÉER
│
├── templates/                           # ✅ NOUVEAU DOSSIER - À CRÉER
│   └── twiyungunganye/                 # (templates HTML à créer)
│
├── manage.py                            # (déjà existant - ne pas modifier)
├── db.sqlite3                           # (sera créé automatiquement)
├── requirements.txt                     # ✅ NOUVEAU FICHIER - À CRÉER
├── README.md                            # ✅ NOUVEAU FICHIER - À CRÉER
├── install.bat                          # ✅ NOUVEAU FICHIER - À CRÉER
└── generate_test_data.py                # ✅ NOUVEAU FICHIER - À CRÉER
```

## ÉTAPES D'INSTALLATION

### ÉTAPE 1: Remplacer les fichiers existants

1. **cotisation/settings.py**
   - Ouvrez le fichier téléchargé `settings_updated.py`
   - Copiez tout son contenu
   - Remplacez le contenu de `C:\Users\MSC KEVIN\Desktop\projectsdjango\cotisation\cotisation\settings.py`

2. **cotisation/urls.py**
   - Ouvrez le fichier téléchargé `urls_projet.py`
   - Copiez tout son contenu
   - Remplacez le contenu de `C:\Users\MSC KEVIN\Desktop\projectsdjango\cotisation\cotisation\urls.py`

3. **twiyungunganye/models.py**
   - Ouvrez le fichier téléchargé `models.py`
   - Copiez tout son contenu
   - Remplacez le contenu de `C:\Users\MSC KEVIN\Desktop\projectsdjango\cotisation\twiyungunganye\models.py`

4. **twiyungunganye/views.py**
   - Ouvrez le fichier téléchargé `views.py`
   - Copiez tout son contenu
   - Remplacez le contenu de `C:\Users\MSC KEVIN\Desktop\projectsdjango\cotisation\twiyungunganye\views.py`

5. **twiyungunganye/admin.py**
   - Ouvrez le fichier téléchargé `admin.py`
   - Copiez tout son contenu
   - Remplacez le contenu de `C:\Users\MSC KEVIN\Desktop\projectsdjango\cotisation\twiyungunganye\admin.py`

### ÉTAPE 2: Créer les nouveaux fichiers

1. **twiyungunganye/forms.py**
   - Créez un nouveau fichier `forms.py` dans `C:\Users\MSC KEVIN\Desktop\projectsdjango\cotisation\twiyungunganye\`
   - Copiez le contenu du fichier téléchargé `forms.py`

2. **twiyungunganye/urls.py**
   - Créez un nouveau fichier `urls.py` dans `C:\Users\MSC KEVIN\Desktop\projectsdjango\cotisation\twiyungunganye\`
   - Copiez le contenu du fichier téléchargé `urls_app.py`

3. **twiyungunganye/pdf_reports.py**
   - Créez un nouveau fichier `pdf_reports.py` dans `C:\Users\MSC KEVIN\Desktop\projectsdjango\cotisation\twiyungunganye\`
   - Copiez le contenu du fichier téléchargé `pdf_reports.py`

4. **requirements.txt**
   - Créez un nouveau fichier `requirements.txt` dans `C:\Users\MSC KEVIN\Desktop\projectsdjango\cotisation\`
   - Copiez le contenu du fichier téléchargé `requirements.txt`

5. **README.md**
   - Créez un nouveau fichier `README.md` dans `C:\Users\MSC KEVIN\Desktop\projectsdjango\cotisation\`
   - Copiez le contenu du fichier téléchargé `README.md`

6. **install.bat**
   - Créez un nouveau fichier `install.bat` dans `C:\Users\MSC KEVIN\Desktop\projectsdjango\cotisation\`
   - Copiez le contenu du fichier téléchargé `install.bat`

7. **generate_test_data.py**
   - Créez un nouveau fichier `generate_test_data.py` dans `C:\Users\MSC KEVIN\Desktop\projectsdjango\cotisation\`
   - Copiez le contenu du fichier téléchargé `generate_test_data.py`

### ÉTAPE 3: Créer les dossiers nécessaires

Dans `C:\Users\MSC KEVIN\Desktop\projectsdjango\cotisation\`, créez ces dossiers:
- `static`
- `media`
- `media\logos`
- `templates`
- `templates\twiyungunganye`

### ÉTAPE 4: Installation automatique

1. Double-cliquez sur `install.bat` pour installer automatiquement les dépendances et configurer la base de données.

OU exécutez manuellement:

```cmd
cd C:\Users\MSC KEVIN\Desktop\projectsdjango\cotisation
pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
```

### ÉTAPE 5: Créer un superutilisateur

```cmd
python manage.py createsuperuser
```

Suivez les instructions pour créer votre compte administrateur.

### ÉTAPE 6: Générer des données de test (optionnel)

```cmd
python generate_test_data.py
```

### ÉTAPE 7: Lancer le serveur

```cmd
python manage.py runserver
```

Ouvrez votre navigateur sur: http://127.0.0.1:8000/

## ORDRE D'IMPORTANCE DES FICHIERS

### 🔴 CRITIQUES (doivent absolument être remplacés):
1. settings.py
2. models.py
3. admin.py
4. views.py

### 🟡 TRÈS IMPORTANTS (nouveaux fichiers essentiels):
5. forms.py
6. urls.py (dans twiyungunganye/)
7. pdf_reports.py
8. requirements.txt

### 🟢 UTILES (pour l'installation et les tests):
9. README.md
10. install.bat
11. generate_test_data.py

## NOTES IMPORTANTES

⚠️ **ATTENTION**: 
- Faites une sauvegarde de vos fichiers existants avant de les remplacer
- Ne modifiez pas les fichiers `__init__.py`, `asgi.py`, `wsgi.py` existants
- Le fichier `db.sqlite3` sera recréé lors des migrations

✅ **VÉRIFICATION**: 
Après installation, vérifiez que vous avez bien:
- Tous les fichiers Python (.py)
- Les dossiers static/, media/, templates/
- Le fichier requirements.txt
- La base de données db.sqlite3 (créée automatiquement)

## BESOIN D'AIDE?

Si vous rencontrez des erreurs:
1. Vérifiez que tous les fichiers sont bien copiés
2. Assurez-vous que Python et pip sont installés
3. Vérifiez que vous êtes dans le bon dossier
4. Lisez attentivement les messages d'erreur
