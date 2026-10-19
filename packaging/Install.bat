@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "TARGET=%LOCALAPPDATA%\DuneMarket"

if not exist "app\DuneMarket.exe" (
    echo Please unzip the whole folder first, then run Install.bat from inside it.
    pause
    exit /b 1
)

echo Installing Dune Market to:
echo   %TARGET%
echo.
taskkill /im DuneMarket.exe /f >nul 2>&1

rem Copy the program. An existing config.toml and prices.db (an upgrade) are kept.
robocopy "app" "%TARGET%" /E /XF config.toml prices.db /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (
    echo Copying failed.
    pause
    exit /b 1
)
if not exist "%TARGET%\config.toml" copy /y "app\config.toml" "%TARGET%\config.toml" >nul

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-helper.ps1" -Target "%TARGET%"
if errorlevel 1 (
    echo.
    echo Something went wrong. Please send a screenshot of this window to the person who gave you the program.
    pause
    exit /b 1
)

echo.
echo Done! Start the game, then double-click "Dune Market" on your desktop.
echo See README.txt for how to use it.
echo.
pause
