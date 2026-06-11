@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
echo Starting Sky Companion...
cd /d "%~dp0"
python main.py
pause
