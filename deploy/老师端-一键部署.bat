@echo off
chcp 65001 >nul
title CallCenter Teacher Deploy
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

echo Starting teacher app ...
start "" /D "%DEST%" "%DEST%\call-center.exe" --role teacher

echo.
echo ============================================
echo  Done. Login with the account your admin
echo  created. Type pinyin initials (lhw), Enter
echo  to pick, Space to multi-select, Enter to
echo  compose, Enter to send.
echo ============================================
pause
