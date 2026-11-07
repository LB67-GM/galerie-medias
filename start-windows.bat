@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
call "%~dp0scripts\galerie-text.bat"
title Galerie Médias
set "SETUP_ONLY=0"
if /I "%~1"=="--setup-only" set "SETUP_ONLY=1"

echo.
echo  ========================================
if "!SETUP_ONLY!"=="1" (
  echo   !M_SETUP!
) else (
  echo   !M_TITLE!
)
echo  ========================================
echo.
echo  !M_PHOTOS!
echo  !M_BASE1!
echo  !M_BASE2!
echo  !M_GUIDE!
echo.

call :find_python
if errorlevel 1 goto :no_python

if exist ".venv\Scripts\python.exe" goto :have_venv
echo !M_FIRST!
if exist .venv rd /s /q .venv 2>nul
"%PY%" -m venv .venv
if errorlevel 1 (
  echo.
  echo !M_VENV!
  pause
  exit /b 1
)
del /q ".deps-ok" 2>nul

:have_venv
set "DEPS_HASH="
for /f "usebackq delims=" %%H in (`"%PY%" scripts\lire_paquets.py --hash`) do set "DEPS_HASH=%%H"
set "OLD_HASH="
if exist ".deps-ok" set /p OLD_HASH=<.deps-ok
if "!OLD_HASH!"=="!DEPS_HASH!" goto :after_deps
echo.
echo !M_PIP!
echo.
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :pip_fail
"%PY%" scripts\lire_paquets.py --write .paquets.txt
if errorlevel 1 goto :pip_fail
".venv\Scripts\python.exe" -m pip install -r .paquets.txt
if errorlevel 1 goto :pip_fail
>".deps-ok" (echo !DEPS_HASH!)

:after_deps
if "!SETUP_ONLY!"=="1" goto :setup_done

echo.
echo !M_FW!
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\allow_firewall_windows.ps1"

set "LANIP="
for /f "delims=" %%I in ('powershell -NoProfile -Command "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } | Select-Object -ExpandProperty IPAddress -First 1"') do set "LANIP=%%I"
echo.
echo  !M_HERE!
if defined LANIP echo  !M_PHONE! https://%LANIP%:8765
echo  !M_VISIT!
echo.
echo  !M_KEEP!
echo.
start "" "https://127.0.0.1:8765/"
".venv\Scripts\python.exe" run.py --portable serve --host 0.0.0.0 --port 8765
echo.
echo !M_STOP!
pause
exit /b 0

:setup_done
echo.
echo  !M_READY!
echo  !M_THEN!
echo  !M_LATER!
echo.
pause
exit /b 0

:pip_fail
echo !M_PIPFAIL!
pause
exit /b 1

:no_python
echo.
echo  ========================================
echo   !M_NOPY!
echo  ========================================
echo.
echo  !M_STORE!
echo  !M_NEED!
echo.
echo  !M_TODO!
echo  1. https://www.python.org/downloads/
echo  !M_STEP2!
echo  !M_STEP3!
echo  !M_STEP4!
echo  !M_STEP5!
echo.
echo  !M_EXPECT!
echo  %LocalAppData%\Programs\Python\Python3XX\python.exe
echo.
start "" "https://www.python.org/downloads/"
pause
exit /b 1

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
