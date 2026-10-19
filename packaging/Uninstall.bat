@echo off
setlocal EnableExtensions
set "TARGET=%LOCALAPPDATA%\DuneMarket"
echo This removes Dune Market from your computer:
echo   %TARGET%
echo and the "Dune Market" desktop shortcut. Prices saved on this computer are deleted too
echo (the shared prices stay in the shared database).
echo.
choice /m "Remove it now"
if errorlevel 2 exit /b 0
taskkill /im DuneMarket.exe /f >nul 2>&1
powershell -NoProfile -Command "Remove-Item -LiteralPath (Join-Path ([Environment]::GetFolderPath('Desktop')) 'Dune Market.lnk') -ErrorAction SilentlyContinue"
rmdir /s /q "%TARGET%"
echo Removed.
pause
