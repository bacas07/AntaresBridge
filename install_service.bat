@echo off
title Instalar Antares Bridge como servicio (Task Scheduler)
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_service.ps1"
echo.
pause
