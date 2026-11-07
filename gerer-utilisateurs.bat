@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

if /I not "%~1"=="__INNER__" (
  cmd /k call "%~f0" __INNER__ %*
  exit /b
)
shift /1

title Galerie Médias - comptes
echo.
echo  ========================================
echo   Galerie Médias - comptes
echo  ========================================
echo.
echo  Lister :
echo    gerer-utilisateurs.bat --list
echo  Creer (role admin ou lecture) :
echo    gerer-utilisateurs.bat --create IDENTIFIANT --role lecture
echo  Mot de passe / pause (aucun e-mail) :
echo    gerer-utilisateurs.bat --set-password IDENTIFIANT
echo  Deverrouiller (meme mot de passe) :
echo    gerer-utilisateurs.bat --unlock IDENTIFIANT
echo  Effacer :
echo    gerer-utilisateurs.bat --delete IDENTIFIANT --yes
echo.

call :find_python
if errorlevel 1 goto :fin

echo.

if "!PY!"=="py -3" (
  py -3 run.py --portable users %*
) else (
  "%PY%" run.py --portable users %*
)

:fin
echo.
echo  --- fin ---  (tapez exit pour fermer)
echo.
goto :eof

:find_python
set "PY="
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info>=(3,10) else 1)" 2>nul
  if not errorlevel 1 (
    set "PY=.venv\Scripts\python.exe"
    echo  Python OK : .venv
    exit /b 0
  )
)
where py >nul 2>&1
if not errorlevel 1 (
  py -3 -c "import sys; raise SystemExit(0 if sys.version_info>=(3,10) else 1)" 2>nul
  if not errorlevel 1 (
    set "PY=py -3"
    echo  Python OK : py -3
    exit /b 0
  )
)
where python >nul 2>&1
if not errorlevel 1 (
  python -c "import sys; raise SystemExit(0 if sys.version_info>=(3,10) else 1)" 2>nul
  if not errorlevel 1 (
    set "PY=python"
    echo  Python OK : python
    exit /b 0
  )
)
for /d %%D in ("%LocalAppData%\Programs\Python\Python3*") do (
  if exist "%%D\python.exe" (
    "%%D\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info>=(3,10) else 1)" 2>nul
    if not errorlevel 1 (
      set "PY=%%D\python.exe"
      echo  Python OK : %%D\python.exe
      exit /b 0
    )
  )
)
echo.
echo  PYTHON introuvable. Lancez preparer-python.bat
echo.
exit /b 1
