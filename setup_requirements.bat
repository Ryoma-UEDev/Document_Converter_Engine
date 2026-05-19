@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PY_VERSION=3.12.10"
set "PY_DIR=%CD%\.standalone\python"
set "PY_EXE=%PY_DIR%\python.exe"
set "DOWNLOAD_DIR=%CD%\.standalone\downloads"
set "PY_ZIP=%DOWNLOAD_DIR%\python-%PY_VERSION%-embed-amd64.zip"
set "PY_URL=https://www.python.org/ftp/python/%PY_VERSION%/python-%PY_VERSION%-embed-amd64.zip"
set "GET_PIP=%DOWNLOAD_DIR%\get-pip.py"
set "GET_PIP_URL=https://bootstrap.pypa.io/get-pip.py"
set "PYTHONNOUSERSITE=1"
set "PYTHONPATH="

echo.
echo Document Converter standalone setup
echo -----------------------------------

if not exist "%PY_EXE%" (
  echo Local Python not found.
  echo Downloading embeddable Python %PY_VERSION%...
  if not exist "%DOWNLOAD_DIR%" mkdir "%DOWNLOAD_DIR%"
  powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%PY_URL%' -OutFile '%PY_ZIP%' -UseBasicParsing"
  if errorlevel 1 (
    echo.
    echo Failed to download Python from:
    echo %PY_URL%
    echo Check internet access, then run this file again.
    exit /b 1
  )

  echo Extracting local Python into:
  echo %PY_DIR%
  if exist "%PY_DIR%" rmdir /s /q "%PY_DIR%"
  mkdir "%PY_DIR%"
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%PY_ZIP%' -DestinationPath '%PY_DIR%' -Force; $pth = Join-Path '%PY_DIR%' 'python312._pth'; if (Test-Path $pth) { (Get-Content -LiteralPath $pth) -replace '#import site','import site' | Set-Content -LiteralPath $pth -Encoding ASCII }"
  if errorlevel 1 (
    echo.
    echo Python extraction failed.
    exit /b 1
  )
)

if not exist "%PY_EXE%" (
  echo.
  echo Local Python install did not create:
  echo %PY_EXE%
  exit /b 1
)

if not exist "%GET_PIP%" (
  echo.
  echo Downloading pip bootstrap...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%GET_PIP_URL%' -OutFile '%GET_PIP%' -UseBasicParsing"
  if errorlevel 1 (
    echo.
    echo Failed to download pip bootstrap from:
    echo %GET_PIP_URL%
    exit /b 1
  )
)

echo.
echo Installing pip into standalone Python...
"%PY_EXE%" "%GET_PIP%"
if errorlevel 1 exit /b 1

echo.
echo Installing backend requirements...
"%PY_EXE%" -m pip install --upgrade pip
if errorlevel 1 exit /b 1

"%PY_EXE%" -m pip install --no-warn-script-location -r backend\requirements.txt
if errorlevel 1 exit /b 1

echo.
echo Standalone setup complete.
echo Run serverstart.bat to start the app.
endlocal
