@echo off
title Cheshire Horse - ShipStation Order Aging Tool
cd /d "%~dp0"

echo.
echo   Cheshire Horse - ShipStation Order Aging Tool
echo   ================================================
echo.

:: Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo   ERROR: Python not found.
    echo   Please install Python from python.org
    echo   and make sure to check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)

:: Set up virtual environment if it doesn't exist
if not exist ".venv\Scripts\activate.bat" (
    echo   Setting up virtual environment for the first time...
    python -m venv .venv
    if errorlevel 1 (
        echo   ERROR: Could not create virtual environment.
        pause
        exit /b 1
    )
)

:: Activate venv
call .venv\Scripts\activate.bat

:: Install/update dependencies
echo   Checking dependencies...
pip install -q flask requests
if errorlevel 1 (
    echo   ERROR: Could not install dependencies.
    pause
    exit /b 1
)

echo.
echo   Starting ShipStation Order Aging Tool...
echo   Your browser will open automatically.
echo   Press Ctrl+C in this window to stop the tool.
echo.

python shipstation_fulfillment_dashboard.py

pause
