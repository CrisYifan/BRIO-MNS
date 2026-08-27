@echo off
setlocal
cd /d "%~dp0"
python run_experiments.py --protocol multibaseline
pause
