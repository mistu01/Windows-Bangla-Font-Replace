@echo off
title Restore Original Windows Bangla Font (Nirmala UI)
color 0E

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
echo     Restoring Original Windows Bangla Font (Nirmala UI)
echo ========================================================
echo.

python "%~dp0replace_bangla.py" --restore

echo.
echo Press any key to exit...
pause >nul
