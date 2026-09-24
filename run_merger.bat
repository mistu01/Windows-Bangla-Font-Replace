@echo off
title Nirmala UI Bengali Font Merger
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
echo         Nirmala UI Bengali Font Merger Launcher
echo ========================================================
echo.

python "%~dp0merge_nirmala.py"

echo.
echo Press any key to exit...
pause >nul
