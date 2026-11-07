@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Galerie Médias - reparation

set "LOG=%~dp0reparer-installation.log"
> "%LOG%" (
  echo ==== %DATE% %TIME% ====
  echo dossier=%CD%
)

echo.
echo  Optionnel : seulement si le site ne demarre plus,
echo  ou apres une nouvelle version du zip.
echo.
echo  Diagnostic : "%LOG%"
echo  (envoyez-moi ce fichier s'il y a un probleme)
echo.

if exist "start-windows.bat" (
  echo start-windows.bat=OUI>> "%LOG%"
  echo  start-windows.bat : present
) else (
  echo start-windows.bat=NON>> "%LOG%"
  echo.
  echo  start-windows.bat introuvable dans :
  echo    %CD%
  echo  Decompressez tout le zip dans un dossier, puis relancez.
  echo.
  echo  Voir "%LOG%"
  pause
  exit /b 1
)

if not exist "scripts\diag_python.py" (
  echo scripts\diag_python.py=NON>> "%LOG%"
  echo  scripts\diag_python.py manquant. Decompressez tout le zip.
  pause
  exit /b 1
)

call :find_python
if errorlevel 1 (
  echo python=INTROUVABLE>> "%LOG%"
  echo.>> "%LOG%"
  echo --- where python --->> "%LOG%"
  where python >> "%LOG%" 2>&1
  echo --- where py --->> "%LOG%"
  where py >> "%LOG%" 2>&1
  echo PATH=%PATH%>> "%LOG%"
  echo.
  echo  Python python.org introuvable (l'alias Store est ignore).
  echo  Voir REQUIS-fr.md (en, es, de) puis preparer-python.bat
  echo  Diagnostic : "%LOG%"
  pause
  exit /b 1
)

echo python_cmd=!PY!>> "%LOG%"
"%PY%" -c "import sys; print('executable='+sys.executable); print('version='+sys.version.replace(chr(10),' ')); print('store='+('OUI' if 'WindowsApps' in sys.executable.replace(chr(92),'/') else 'NON'))" >> "%LOG%" 2>&1
if errorlevel 1 (
  echo python_run=ECHEC>> "%LOG%"
  echo  Python refuse d'executer une commande. Voir "%LOG%"
  pause
  exit /b 1
)

"%PY%" "%~dp0scripts\diag_python.py" --log "%LOG%"
if errorlevel 1 (
  echo.
  echo  Python incorrect (Microsoft Store) ou start-windows.bat absent.
  echo  Diagnostic : "%LOG%"
  pause
  exit /b 1
)

echo.
echo  Python python.org OK. Reinstallation des programmes (.venv).
echo.
del /q ".deps-ok" 2>nul
call start-windows.bat
goto :eof

:accept_py
echo %~1 | findstr /I /C:"WindowsApps" >nul
if not errorlevel 1 exit /b 1
if not exist "%~1" exit /b 1
"%~1" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" 2>nul
exit /b %errorlevel%

:try_set
call :accept_py "%~1"
if errorlevel 1 exit /b 1
set "PY=%~1"
exit /b 0

:find_python
set "PY="
for /d %%D in ("%LocalAppData%\Programs\Python\Python3*") do (
  call :try_set "%%D\python.exe"
  if defined PY exit /b 0
)
for /d %%D in ("%ProgramFiles%\Python3*") do (
  call :try_set "%%D\python.exe"
  if defined PY exit /b 0
)
where py >nul 2>&1
if %errorlevel%==0 (
  for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do (
    call :try_set "%%P"
    if defined PY exit /b 0
  )
)
where python >nul 2>&1
if %errorlevel%==0 (
  for /f "delims=" %%P in ('python -c "import sys; print(sys.executable)" 2^>nul') do (
    call :try_set "%%P"
    if defined PY exit /b 0
  )
)
exit /b 1
