@echo off
echo ========================================
echo Installation de l'application Cotisation
echo ========================================
echo.

echo Etape 1: Installation des dependances...
pip install -r requirements.txt
if errorlevel 1 (
    echo Erreur lors de l'installation des dependances!
    pause
    exit /b 1
)
echo.

echo Etape 2: Creation des dossiers necessaires...
if not exist "static" mkdir static
if not exist "media" mkdir media
if not exist "media\logos" mkdir media\logos
if not exist "templates" mkdir templates
echo Dossiers crees avec succes!
echo.

echo Etape 3: Application des migrations...
python manage.py makemigrations
if errorlevel 1 (
    echo Erreur lors de la creation des migrations!
    pause
    exit /b 1
)

python manage.py migrate
if errorlevel 1 (
    echo Erreur lors de l'application des migrations!
    pause
    exit /b 1
)
echo Migrations appliquees avec succes!
echo.

echo ========================================
echo Installation terminee avec succes!
echo ========================================
echo.
echo Prochaines etapes:
echo 1. Executez: python manage.py createsuperuser
echo    (pour creer un compte administrateur)
echo.
echo 2. Executez: python manage.py runserver
echo    (pour lancer le serveur)
echo.
echo 3. Ouvrez votre navigateur sur: http://127.0.0.1:8000/
echo.
pause
