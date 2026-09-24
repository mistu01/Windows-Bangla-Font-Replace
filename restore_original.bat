@echo off
title Restore Original Windows Nirmala Font
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
echo         Restoring Original Windows Nirmala Font
echo ========================================================
echo.

python "%~dp0merge_nirmala.py" --restore

echo.
echo Press any key to exit...
pause >nul
