@echo off
chcp 65001 >nul
title CallCenter Server Deploy
set DEST=C:\CallCenter
rem pick newest call-center-*-x64.exe next to this script (version-agnostic)
set EXE=
for /f "delims=" %%F in ('dir /b /o-d "%~dp0call-center-*-x64.exe" 2^>nul') do set EXE=%~dp0%%F

if not exist "%EXE%" (
  echo [ERROR] no call-center-*-x64.exe found next to this script.
  pause
  exit /b 1
)
rem stop any running instance first: copy over a running exe fails (M2)
taskkill /F /IM call-center.exe >nul 2>&1
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
