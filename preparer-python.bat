@echo off
cd /d "%~dp0"
if not exist "start-windows.bat" (
  echo start-windows.bat introuvable.
  pause
  exit /b 1
)
call "%~dp0start-windows.bat" --setup-only
