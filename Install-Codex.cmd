@echo off
call "%~dp0Install-arizdot.cmd" %* --target codex
exit /b %errorlevel%
