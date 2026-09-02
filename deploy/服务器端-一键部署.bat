@echo off
chcp 65001 >nul
title CallCenter Server Deploy
set DEST=C:\CallCenter
set EXE=%~dp0call-center-0.1.4-x64.exe

if not exist "%EXE%" (
  echo [ERROR] call-center-0.1.4-x64.exe not found next to this script.
  pause
  exit /b 1
)
if not exist "%DEST%" mkdir "%DEST%"
echo Copying to %DEST% ...
copy /Y "%EXE%" "%DEST%\call-center.exe" >nul
if errorlevel 1 (
  echo [ERROR] copy failed.
  pause
  exit /b 1
)

echo Setting up autostart ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0_setup_autostart.ps1" -Role server

echo Starting server ...
start "" /D "%DEST%" "%DEST%\call-center.exe" --role server

echo.
echo ============================================
echo  Done. Next two steps:
echo   1. Firewall popup: Allow access + Private
echo   2. Create the admin account in the window
echo  Admin console: teachers, classes, rosters.
echo ============================================
pause
