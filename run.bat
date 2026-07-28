@echo off
title Antares Bridge
cd /d "%~dp0"

echo ========================================
echo   Antares Bridge
echo ========================================
echo.

REM ── Detectar Python ────────────────────────────────────────────
set PYTHON=
python --version >nul 2>nul
if %errorlevel% equ 0 (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>nul
    if %errorlevel% equ 0 set PYTHON=python
)

if "%PYTHON%"=="" (
    echo.
    echo  ********************************************
    echo  *  ERROR: Python 3.8+ no esta instalado.  *
    echo  ********************************************
    echo.
    echo  Esta maquina tiene Windows Server 2012.
    echo  Necesitas instalar Python 3.9 (ultima
    echo  version compatible con WS2012).
    echo.
    echo  PASOS:
    echo  1. Descarga Python 3.9.13 para Windows:
    echo     https://www.python.org/ftp/python/3.9.13/python-3.9.13-amd64.exe
    echo.
    echo  2. Ejecuta el instalador.
    echo     - MARCA "Add Python 3.9 to PATH"
    echo     - Haz clic en "Install Now"
    echo.
    echo  3. Abre una NUEVA terminal cmd y ejecuta:
    echo     python run.py
    echo.
    pause
    exit /b 1
)

echo [OK] Python encontrado.
echo.

REM ── Dejar que run.py haga el resto ────────────────────────────
%PYTHON% run.py
pause
