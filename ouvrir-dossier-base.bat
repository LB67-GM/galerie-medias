@echo off
setlocal EnableExtensions
title Galerie Médias - dossier de la base
if not defined APPDATA (
  echo Windows n'a pas trouve APPDATA.
  pause
  exit /b 1
)
if not exist "%APPDATA%\GaleriePhotos" mkdir "%APPDATA%\GaleriePhotos"
echo.
echo  Voici le dossier de la BASE (SQLite, reglages, miniatures).
echo  Ce n'est PAS le dossier des photos.
echo.
echo  %APPDATA%\GaleriePhotos
echo.
explorer "%APPDATA%\GaleriePhotos"
pause
