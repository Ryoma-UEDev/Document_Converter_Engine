@echo off
setlocal
cd /d "%~dp0.."

set "PYTHONNOUSERSITE=1"
set "PYTHONPATH="
set "PYTHON_EXE="
if exist ".standalone\python\python.exe" (
  set "PYTHON_EXE=%CD%\.standalone\python\python.exe"
)

if "%PYTHON_EXE%"=="" (
  if not exist .venv (
    echo Python environment missing.
    echo Run Win\setup_requirements.bat for standalone setup, or Win\serversetup.bat if Python is already installed.
    exit /b 1
  )
  call .venv\Scripts\activate.bat
  set "PYTHON_EXE=python"
)

start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://localhost:8000/'"
"%PYTHON_EXE%" -m uvicorn backend.server:app --host 0.0.0.0 --port 8000
endlocal
