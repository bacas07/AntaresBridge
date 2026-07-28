@echo off
cd /d "%~dp0"

echo.
echo ========================================
echo   Antares Bridge
echo ========================================
echo.

REM ── Detectar Python ────────────────────────────────────────────
set PYTHON=
for %%C in (python3 python py) do (
    where %%C >nul 2>nul
    if not errorlevel 1 (
        for /f "tokens=*" %%V in ('%%C --version 2^>^&1') do set VER=%%V
        echo %%V | findstr /R "^Python 3" >nul
        if not errorlevel 1 (
            set PYTHON=%%C
            goto :found_python
        )
    )
)
:found_python

if "%PYTHON%"=="" (
    echo [ERROR] No se encontro Python 3.
    echo.
    echo   Instala Python 3.8+ desde https://www.python.org/downloads/
    echo   Asegurate de marcar "Add Python to PATH" durante la instalacion.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%V in ('%PYTHON% --version 2^>^&1') do set PYVER=%%V
echo [OK] Python: %PYVER%

REM ── Crear venv si no existe ────────────────────────────────────
if not exist "venv" (
    echo Creando entorno virtual...
    %PYTHON% -m venv venv
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el venv.
        pause
        exit /b 1
    )
) else (
    echo [OK] Entorno virtual existente.
)

REM ── Activar venv ───────────────────────────────────────────────
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo [ERROR] No se encontro activate en el venv.
    pause
    exit /b 1
)

REM ── Verificar .env ─────────────────────────────────────────────
if not exist ".env" (
    echo [AVISO] Archivo .env no encontrado.
    copy .env.example .env >nul
    echo   Se creo desde .env.example.
    echo.
    echo   ¡EDITA .env antes de continuar!
    echo   Debes configurar al menos:
    echo     ANTARES_SERVER = IP/hostname del MySQL
    echo     AGENDA_SYSTEM_URL = URL del sistema de agenda
    echo.
    pause
    exit /b 1
)

REM ── Instalar dependencias ──────────────────────────────────────
echo Instalando dependencias...
pip install --quiet -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Fallo la instalacion de dependencias.
    echo.
    echo   Intenta manualmente:
    echo     venv\Scripts\activate.bat
    echo     pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)
echo [OK] Dependencias instaladas.

REM ── Verificar credenciales Docker ──────────────────────────────
findstr /C:"host.docker.internal" .env >nul 2>nul
if not errorlevel 1 (
    echo [AVISO] .env contiene hostnames Docker ^(host.docker.internal^).
    echo   Actualiza ANTARES_SERVER y AGENDA_SYSTEM_URL si ejecutas sin Docker.
    echo.
)

REM ── Iniciar ────────────────────────────────────────────────────
echo.
echo Iniciando Antares Bridge...
echo   Dashboard: http://localhost:8001
echo   Ctrl+C para detener
echo.

python -m src.main

echo.
echo El proceso termino.
pause
