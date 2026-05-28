@echo off
setlocal
cd /d "%~dp0.."
if not exist .venv (
  py -3 -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r backend\requirements.txt

echo.
echo Server dependencies installed.
endlocal
