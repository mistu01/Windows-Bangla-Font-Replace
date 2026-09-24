@echo off
title Windows Bangla Font Replacer (Nirmala UI)
color 0B

:: Ensure Administrator privileges
fltmc >nul 2>&1 || (
    echo ========================================================
    echo   Requesting Administrator privileges...
    echo ========================================================
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"
echo ========================================================
echo         Windows Bangla Font Replacer Launcher
echo ========================================================
echo.

python "%~dp0replace_bangla.py"

echo.
echo Press any key to exit...
pause >nul
