@echo off
title Cheshire Horse - Weekly Fulfillment Report
cd /d "%~dp0"

echo.
echo   Cheshire Horse - Weekly Fulfillment Report
echo   =============================================
echo.

if not exist ".venv\Scripts\activate.bat" (
    echo   ERROR: No virtual environment found.
    echo   Run start_dashboard_tool.bat once first to set it up.
    echo.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
python weekly_report.py
if errorlevel 1 (
    echo.
    echo   Something went wrong - see the error above.
)

echo.
pause
