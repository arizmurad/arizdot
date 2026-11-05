@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Install arizdot first with Install-arizdot.cmd.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" connect_kaggle.py --login
pause
