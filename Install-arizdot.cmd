@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto python
py -3 "%~dp0install_windows.py" %*
goto finished
:python
python "%~dp0install_windows.py" %*
:finished
if errorlevel 1 goto failed
if "%~1"=="--check" exit /b 0
echo.
pause
exit /b 0
:failed
echo.
echo Setup did not complete. Read the message above.
if "%~1"=="--check" exit /b 1
pause
exit /b 1
