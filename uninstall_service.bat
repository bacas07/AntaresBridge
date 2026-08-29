@echo off
title Quitar servicio Antares Bridge
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_service.ps1" -Uninstall
echo.
pause
