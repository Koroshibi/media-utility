@echo off
cd /d "%~dp0"
python -c "import customtkinter, tkinterdnd2" 2>nul || python -m pip install -r requirements.txt || (echo Python introuvable ou installation impossible. Installez Python depuis https://python.org & pause & exit /b 1)
start "" pythonw media_toolkit.py %*
