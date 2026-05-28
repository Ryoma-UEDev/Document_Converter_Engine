@echo off
setlocal
cd /d "%~dp0"
set "PORT=8050"
set "PYTHON_EXE=python"
if exist "..\..\.standalone\python\python.exe" set "PYTHON_EXE=..\..\.standalone\python\python.exe"
start "" "http://localhost:%PORT%/"
"%PYTHON_EXE%" server.py --port %PORT%
pause
