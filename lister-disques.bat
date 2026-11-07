@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Galerie Médias - disques
echo.
echo  Branchez le disque USB, attendez quelques secondes,
echo  puis lisez la liste ci-dessous.
echo.
powershell -NoProfile -Command "Get-CimInstance Win32_LogicalDisk | ForEach-Object { $t = switch ($_.DriveType) { 2 {'USB'} 3 {'Interne'} 4 {'Reseau'} 5 {'DVD'} default {'Autre'} }; $g = if ($_.Size) { [math]::Round($_.Size/1GB,0) } else { 0 }; $l = if ($_.FreeSpace) { [math]::Round($_.FreeSpace/1GB,0) } else { 0 }; $n = $_.VolumeName; if (-not $n) { $n = '(sans nom)' }; '{0}  {1,-22}  {2,-8}  {3} Go ({4} Go libres)' -f $_.DeviceID, $n, $t, $g, $l }"
echo.
echo  Dans la galerie : onglet Reglages.
echo  Si le USB est E: et vos photos sont dans le dossier Photos,
echo  ecrivez :  E:\Photos
echo.
echo  Si Windows change la lettre (E: devient F:),
echo  mettez a jour Reglages, Enregistrer, puis relancez la galerie.
echo.
pause
