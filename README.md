# Application de Gestion des Cotisations

Application web Django pour la gestion des cotisations mensuelles des travailleurs avec système de crédit et remboursement.

## Fonctionnalités

### Pour les Administrateurs
- Gestion complète des membres (ajout, modification, suppression)
- Enregistrement des cotisations mensuelles
- Approbation/rejet des demandes de crédit
- Enregistrement des remboursements
- Génération de rapports mensuels et annuels en PDF
- Gestion des droits d'accès (administrateur, gestionnaire)
- Consultation des suggestions des membres

### Pour les Membres
- Connexion avec carte d'identité et mot de passe
- Consultation de leurs cotisations
- Demande de crédit
- Consultation de l'état de leurs crédits
- Soumission de suggestions
- Visualisation du tableau de bord personnel

### Système de Crédit
- Taux d'intérêt: 5% par mois
- Calcul automatique des intérêts basé sur le nombre de mois
- Suivi des remboursements
- États: En attente, Approuvé, Rejeté, En cours de remboursement, Remboursé

### Rapports
- Rapport mensuel avec:
  - Liste des cotisations du mois
  - Crédits en cours
  - Remboursements du mois
  - Résumé financier
  
- Rapport annuel avec:
  - Cotisations par mois
  - Statistiques des crédits
  - Bilan financier annuel

## Installation

### Prérequis
- Python 3.8 ou supérieur
- pip (gestionnaire de paquets Python)

### Étapes d'installation

1. **Ouvrez un terminal dans le dossier du projet**
   ```
   cd C:\Users\MSC KEVIN\Desktop\projectsdjango\cotisation
   ```

2. **Installez les dépendances**
   ```
   pip install -r requirements.txt
   ```

3. **Appliquez les migrations de base de données**
   ```
   python manage.py makemigrations
   python manage.py migrate
   ```

4. **Créez un superutilisateur (administrateur)**
   ```
   python manage.py createsuperuser
   ```
   Suivez les instructions pour créer votre compte administrateur.

5. **Créez les dossiers nécessaires**
   ```
   mkdir static
   mkdir media
   mkdir templates
   ```

6. **Lancez le serveur de développement**
   ```
   python manage.py runserver
   ```

7. **Accédez à l'application**
   - Interface publique: http://127.0.0.1:8000/
   - Interface d'administration: http://127.0.0.1:8000/admin/
   - Dashboard: http://127.0.0.1:8000/dashboard/

## Configuration initiale

### 1. Configurer l'association

Allez dans l'interface d'administration (http://127.0.0.1:8000/admin/) et créez une entrée dans "Associations" avec:
- Nom de l'association
- Coordonnées
- Montant de la cotisation mensuelle par défaut

### 2. Ajouter des membres

Dans l'interface d'administration, ajoutez des membres avec leurs informations:
- Nom et prénom
- Carte d'identité (sera utilisée comme identifiant de connexion)
- Email et téléphone
- Adresse

### 3. Membres créent leur mot de passe

Les nouveaux membres doivent:
1. Aller sur http://127.0.0.1:8000/creer-mot-de-passe/
2. Entrer leur numéro de carte d'identité
3. Créer leur mot de passe

## Structure de la base de données

### Tables principales

1. **membres**: Informations des membres et authentification
2. **cotisations**: Cotisations mensuelles de chaque membre
3. **credits**: Demandes et approbations de crédits
4. **interets**: Calcul et suivi des intérêts mensuels
5. **remboursements**: Enregistrement des paiements
6. **associations**: Informations de l'association
7. **suggestions**: Suggestions des membres

## Formules utilisées

```
somme_cotisation_membre = cotisation × nombre_mois
interet_membre = somme × 0.05 × nombre_mois
reste_rembourse = interet_membre - interet_rembourse
cotisation_total = cotisation × count(id_membre)
interet_total = interet_membre × count(id_membre)
interet_annuel = interet_total × nombre_mois
cotisation_annuel = cotisation_total × nombre_mois
rembourse_total = sum(somme_rembourse)
cotisation_avec_rembourse = somme_cotisation_membre × rembourse_total
cotisation_avec_rembourse_annuel = cotisation_avec_rembourse × nombre_mois
```

## Technologies utilisées

- **Backend**: Django 6.0.1
- **Base de données**: SQLite3
- **Génération PDF**: ReportLab
- **Frontend**: Bootstrap MDB (Material Design for Bootstrap)
- **Langage**: Python 3.x

## Commandes utiles

### Créer des migrations
```
python manage.py makemigrations
```

### Appliquer les migrations
```
python manage.py migrate
```

### Créer un superutilisateur
```
python manage.py createsuperuser
```

### Lancer le serveur
```
python manage.py runserver
```

### Collecter les fichiers statiques (pour production)
```
python manage.py collectstatic
```

## Sécurité

⚠️ **Important pour la production**:
1. Changez la `SECRET_KEY` dans `settings.py`
2. Mettez `DEBUG = False`
3. Configurez `ALLOWED_HOSTS`
4. Utilisez une base de données PostgreSQL ou MySQL
5. Configurez HTTPS
6. Mettez en place un système de sauvegarde régulier

## Support

Pour toute question ou problème, contactez l'administrateur du système.

## Licence

Application développée pour la gestion des cotisations d'association.
