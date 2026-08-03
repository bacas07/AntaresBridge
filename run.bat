@echo off
title Antares Bridge
cd /d "%~dp0"

echo ========================================
echo   Antares Bridge
echo ========================================
echo.

REM 1. Verificar .env
if not exist ".env" (
    echo ERROR: Archivo .env no encontrado.
    echo   Copialo: copy .env.example .env
    echo   Luego editalo con notepad .env
    pause
    exit /b 1
)

REM 2. Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no encontrado.
    echo   Instala Python 3.9.13 para Windows Server 2012:
    echo   https://www.python.org/ftp/python/3.9.13/python-3.9.13-amd64.exe
    echo   Marca "Add Python to PATH" al instalar.
    echo   Luego abre una NUEVA terminal y vuelve a ejecutar run.bat
    pause
    exit /b 1
)

echo [OK] Python encontrado.

REM 3. Eliminar venv corrupto (macOS/Linux, o dañado)
if exist "venv\pyvenv.cfg" (
    findstr /C:"Library" venv\pyvenv.cfg >nul 2>&1
    if not errorlevel 1 (
        echo Venv de macOS/Linux detectado. Eliminando...
        rmdir /s /q venv
    )
)
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe -c "" >nul 2>&1
    if errorlevel 1 (
        echo Venv corrupto. Eliminando...
        rmdir /s /q venv
    )
)

REM 4. Crear venv si no existe
if not exist "venv\" (
    echo Creando entorno virtual...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: No se pudo crear el entorno virtual.
        echo   python -m venv venv
        pause
        exit /b 1
    )
    echo [OK] Entorno virtual creado.
)

REM 5. Activar venv
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: No se pudo activar el entorno virtual.
    pause
    exit /b 1
)

REM 6. Instalar dependencias
echo Instalando dependencias...
pip install -r requirements.txt
if errorlevel 1 (
    echo   Online fallo, probando offline desde wheels\...
    pip install --no-index --find-links wheels\ -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ERROR: No se pudieron instalar las dependencias.
        echo   Verifica que tengas conexion a internet o la carpeta wheels\
        pause
        exit /b 1
    )
)

REM 7. Arrancar
echo.
echo ========================================
echo   Iniciando Antares Bridge...
echo   Dashboard: http://localhost:8001
echo   Ctrl+C para detener
echo ========================================
echo.

python -m src.main
if errorlevel 1 (
    echo.
    echo ERROR: La aplicacion termino con errores.
)
pause
