@echo off
chcp 65001 >nul
title CallCenter Display Deploy
set DEST=C:\CallCenter
rem pick newest call-center-*-x64.exe next to this script (version-agnostic)
set EXE=
for /f "delims=" %%F in ('dir /b /o-d "%~dp0call-center-*-x64.exe" 2^>nul') do set EXE=%~dp0%%F

if not exist "%EXE%" (
  echo [ERROR] no call-center-*-x64.exe found next to this script.
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
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0_setup_autostart.ps1" -Role display

echo Starting classroom display ...
start "" /D "%DEST%" "%DEST%\call-center.exe" --role display

echo.
echo ============================================
echo  Done. Firewall popup: Allow + Private.
echo  Pick this classroom's class once.
echo  Idle: small corner window (clock).
echo  Calls: auto fullscreen + voice, then back.
echo ============================================
pause
