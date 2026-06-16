@echo off
title Cheshire Horse - Rewards Account Creator
cd /d "%~dp0"

echo.
echo   Cheshire Horse - Rewards Account Creator
echo   ==========================================
echo.

:: Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo   ERROR: Python is not installed or not in PATH.
    echo   Download Python from https://www.python.org/downloads/
    echo   Make sure to check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)

:: Check if Flask is installed
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo   Installing Flask...
    pip install flask
    echo.
)

echo   Starting server at http://localhost:5000
echo   Press Ctrl+C to stop
echo.

python app.py
