@echo off
rem Double-cliquez ce fichier pour ouvrir la galerie (installation comprise la premiere fois).
cd /d "%~dp0"
if not exist "start-windows.bat" (
  echo Fichier start-windows.bat introuvable dans :
  echo   %CD%
  echo Decompressez tout le zip dans un dossier, puis relancez ce fichier.
  pause
  exit /b 1
)
call start-windows.bat
