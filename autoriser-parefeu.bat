@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Galerie Médias - pare-feu
echo.
echo  Autorisation PERMANENTE des ports 8765 (site) et 8766 (TV).
echo  Cliquez Oui dans la fenetre qui s'ouvre.
echo.
echo  Sur cet ordinateur, le site marche meme si vous cliquez Non.
echo  Pour un iPhone ou une TV sur le meme Wi-Fi, acceptez Oui.
echo  Le Wi-Fi Windows doit etre un reseau Prive (pas Public).
echo.
del /q ".firewall-ok" 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\allow_firewall_windows.ps1"
if exist ".firewall-ok" (
  echo Termine. La regle reste apres un reboot.
) else (
  echo La demande a ete refusee ou n'a pas abouti.
  echo Ce n'est pas grave pour un usage sur cet ordinateur.
)
echo.
pause
