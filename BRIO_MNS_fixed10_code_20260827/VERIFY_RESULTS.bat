@echo off
setlocal
cd /d "%~dp0"
python verify_results.py
pause
