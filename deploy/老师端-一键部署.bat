@echo off
chcp 65001 >nul
title CallCenter Teacher Deploy
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
