@echo off
title Windows Segoe UI Family Font Replacer
color 0A

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
echo         Segoe UI Family Font Replacer Launcher
echo ========================================================
echo.

python "%~dp0replace_segoe.py"

echo.
echo Press any key to exit...
pause >nul
