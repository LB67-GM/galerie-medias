@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Galerie Médias - raccourci

set "BAT=%~dp0ouvrir-galerie.bat"
set "PS1=%~dp0scripts\create_desktop_shortcut.ps1"

if not exist "%BAT%" (
  echo Fichier introuvable :
  echo   %BAT%
  pause
  exit /b 1
)
if not exist "%PS1%" (
  echo Script introuvable :
  echo   %PS1%
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" -BatPath "%BAT%" -WorkDir "%CD%"
if errorlevel 1 (
  echo.
  echo Echec. Raccourci manuel :
  echo   clic droit sur ouvrir-galerie.bat - Envoyer vers - Bureau
  pause
  exit /b 1
)

echo.
echo  Double-cliquez "Galerie Médias" sur le Bureau.
echo  Laissez la fenetre noire ouverte pendant que vous utilisez le site.
echo.
pause
