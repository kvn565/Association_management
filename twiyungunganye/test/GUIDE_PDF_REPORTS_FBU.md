# GUIDE RAPIDE - Remplacer pdf_reports.py pour utiliser FBU

## 📍 Emplacement du fichier

Le fichier `pdf_reports.py` doit être placé dans le dossier de votre application Django :

```
C:\Users\MSC KEVIN\Desktop\projectsdjango\cotisationnV1\twiyungunganye\pdf_reports.py
```

## 🔄 Comment remplacer le fichier

### Méthode 1 : Copier-coller (RECOMMANDÉ pour Windows)

1. **Ouvrez l'Explorateur de fichiers**
   - Allez dans : `C:\Users\MSC KEVIN\Desktop\projectsdjango\cotisationnV1\twiyungunganye\`

2. **Localisez le fichier pdf_reports.py**
   - Si le fichier existe déjà, faites une copie de sauvegarde :
     - Clic droit sur `pdf_reports.py`
     - Renommer en `pdf_reports.py.backup`

3. **Copiez le nouveau fichier**
   - Prenez le fichier `pdf_reports.py` que je vous ai fourni
   - Copiez-le dans le dossier `twiyungunganye\`

### Méthode 2 : Via la commande CMD

```cmd
cd C:\Users\MSC KEVIN\Desktop\projectsdjango\cotisationnV1\twiyungunganye

:: Sauvegarder l'ancien fichier (si existe)
ren pdf_reports.py pdf_reports.py.backup

:: Copier le nouveau fichier depuis votre dossier de téléchargement
copy "C:\Users\MSC KEVIN\Downloads\pdf_reports.py" pdf_reports.py
```

## ✅ Vérification

Après avoir remplacé le fichier, vérifiez qu'il fonctionne :

1. **Lancez le serveur**
   ```cmd
   python manage.py runserver
   ```

2. **Testez la génération de PDF**
   - Connectez-vous à l'admin : http://127.0.0.1:8000/admin
   - Allez dans Rapports : http://127.0.0.1:8000/rapports
   - Générez un rapport mensuel ou annuel
   - Le PDF devrait s'ouvrir avec tous les montants en **FBU** au lieu de FC

## 📊 Qu'est-ce qui a changé ?

### Avant (avec FC) :
```
Montant (FC) | Total : 50,000.00 FC
```

### Après (avec FBU) :
```
Montant (FBU) | Total : 50,000.00 FBU
```

## 🔍 Tous les changements effectués

Le fichier `pdf_reports.py` corrigé affiche maintenant FBU dans :

### Rapport Mensuel :
- ✅ Tableau des cotisations : colonne "Montant (FBU)"
- ✅ Ligne de total des cotisations : "XX FBU"
- ✅ Section résumé : tous les montants en FBU

### Rapport Annuel :
- ✅ Tableau cotisations par mois : colonne "Total (FBU)"
- ✅ Statistiques des crédits : tous les montants en FBU
- ✅ Bilan financier : tous les montants en FBU

## 🚨 Que faire en cas de problème

### Erreur : "Module 'reportlab' not found"
**Solution :**
```cmd
pip install reportlab
```

### Erreur : "pdf_reports has no attribute..."
**Solution :** Vérifiez que vous avez bien remplacé le fichier dans le bon dossier

### Les PDF ne s'affichent pas
**Solution :** Vérifiez que le fichier `urls.py` contient bien ces lignes :
```python
path('rapports/mensuel/<int:mois>/<int:annee>/pdf/', pdf_reports.rapport_mensuel_pdf, name='rapport_mensuel_pdf'),
path('rapports/annuel/<int:annee>/pdf/', pdf_reports.rapport_annuel_pdf, name='rapport_annuel_pdf'),
```

## 📝 Note importante

Ce fichier fonctionne avec les modèles que je vous ai fournis précédemment :
- `models.py` (avec FBU)
- `views.py` (avec FBU)
- `admin.py` (avec FBU)
- `forms.py` (avec FBU)

Assurez-vous d'avoir également remplacé tous ces fichiers pour une cohérence complète !

---

**C'est tout ! Votre système génère maintenant des rapports PDF en FBU.** 🎉
