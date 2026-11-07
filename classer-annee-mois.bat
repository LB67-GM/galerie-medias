@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
REM Console Windows (cp1252) : ne pas planter sur des caracteres comme la fleche
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

if /I not "%~1"=="__INNER__" (
  cmd /k call "%~f0" __INNER__ %*
  exit /b
)
shift /1

title Galerie Médias - Annee / mois
set "LOG=%~dp0classer-annee-mois-last.log"
echo ==== %DATE% %TIME% ==== > "%LOG%"

echo.
echo  [classer-annee-mois] demarrage...
echo.

if not exist "tools\sort_annee_mois.py" (
  echo  ERREUR : tools\sort_annee_mois.py introuvable.
  goto :fin
)

call :find_python
if errorlevel 1 goto :fin

set "SRC=%~1"
set "DEST=%~2"
set "EXTRA=%~3"

if "!SRC!"=="" (
  echo  Exemple : E:\Photos
  set /p "SRC=  Dossier SOURCE : "
)
if "!SRC!"=="" (
  echo  Aucun dossier SOURCE. Abandon.
  goto :fin
)
if "!DEST!"=="" (
  echo  Entree = meme dossier que SOURCE
  set /p "DEST=  DESTINATION [meme] : "
)
if "!DEST!"=="" set "DEST=!SRC!"

REM Important: ne pas ecrire "!SRC!\"  (bug cmd = etait inattendu)
if not exist "!SRC!\." (
  echo  SOURCE introuvable : !SRC!
  goto :fin
)

if "!EXTRA!"=="" (
  set "CHOIX=1"
  set /p "CHOIX=  Choix 1=simuler 2=appliquer [1] : "
  if "!CHOIX!"=="2" set "EXTRA=--apply"
)

echo.
echo  SOURCE=!SRC!
echo  DEST  =!DEST!
echo  PY    =!PY!
echo.

if "!PY!"=="py -3" (
  py -3 "tools\sort_annee_mois.py" "!SRC!" "!DEST!" !EXTRA!
) else (
  "%PY%" "tools\sort_annee_mois.py" "!SRC!" "!DEST!" !EXTRA!
)
echo exit=!ERRORLEVEL!>> "%LOG%"

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
