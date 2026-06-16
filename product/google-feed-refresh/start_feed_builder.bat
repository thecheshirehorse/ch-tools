@echo off
cd /d "%~dp0"
echo Starting Google Feed Builder...
python build_feed.py
pause
