@echo off
chcp 65001 >nul
title Media Toolkit
echo ========================================
echo    Media Toolkit
echo ========================================
echo.

:: Verifier Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python n'est pas installe ou n'est pas dans le PATH
    echo.
    echo Veuillez installer Python depuis https://python.org
    echo.
    pause
    exit /b 1
)

echo [OK] Python detecte
echo.

:: Verifier customtkinter
python -c "import customtkinter" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installation de CustomTkinter necessaire...
    echo.
    pip install customtkinter
    if errorlevel 1 (
        echo.
        echo [ERREUR] Impossible d'installer CustomTkinter
        echo Verifiez votre connexion internet
        pause
        exit /b 1
    )
    echo.
    echo [OK] Installation terminee
echo.
)

echo [OK] CustomTkinter detecte
echo.
echo ========================================
echo    Lancement de Media Toolkit...
echo ========================================
echo.

python media_toolkit.py

if errorlevel 1 (
    echo.
    echo [ERREUR] L'application a rencontre un probleme
    pause
)
