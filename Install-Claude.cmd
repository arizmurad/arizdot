@echo off
call "%~dp0Install-arizdot.cmd" %* --target claude
exit /b %errorlevel%
