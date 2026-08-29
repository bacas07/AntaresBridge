@echo off
title Antares Bridge
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
    echo ERROR: venv no encontrado. Ejecuta run.bat primero para crearlo.
    pause
    exit /b 1
)
"venv\Scripts\python.exe" -m src.main
exit /b %errorlevel%
