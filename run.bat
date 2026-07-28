@echo off
title Antares Bridge
cd /d "%~dp0"

echo ========================================
echo   Antares Bridge
echo ========================================
echo.

REM 1. Verificar que .env existe
if not exist ".env" (
    echo ERROR: Archivo .env no encontrado.
    echo   Copialo: copy .env.example .env
    echo   Luego editalo con notepad .env
    pause
    exit /b 1
)

REM 2. Crear venv si no existe
if not exist "venv\" (
    echo Creando entorno virtual...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: No se pudo crear el venv.
        pause
        exit /b 1
    )
)

REM 3. Activar venv
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: No se pudo activar el venv.
    pause
    exit /b 1
)

REM 4. Instalar dependencias
echo Instalando dependencias...
pip install -r requirements.txt
if errorlevel 1 (
    echo Probando instalacion offline...
    pip install --no-index --find-links wheels\ -r requirements.txt
    if errorlevel 1 (
        echo ERROR: No se pudieron instalar las dependencias.
        pause
        exit /b 1
    )
)

REM 5. Arrancar
echo.
echo Iniciando Antares Bridge...
echo Dashboard: http://localhost:8001
echo Ctrl+C para detener
echo.

python -m src.main

pause
