@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

set "OLLAMA_ROOT=%CD%\.standalone\ollama"
set "OLLAMA_BIN=%OLLAMA_ROOT%\bin"
set "OLLAMA_MODELS=%OLLAMA_ROOT%\models"
set "OLLAMA_IMPORTS=%OLLAMA_ROOT%\imports"
set "DOWNLOAD_DIR=%CD%\.standalone\downloads"
set "OLLAMA_ZIP=%DOWNLOAD_DIR%\ollama-windows-amd64.zip"
set "OLLAMA_URL=https://github.com/ollama/ollama/releases/latest/download/ollama-windows-amd64.zip"

echo.
echo Document Converter local Ollama setup
echo ------------------------------------
echo Install folder:
echo %OLLAMA_ROOT%
echo.

if not exist "%DOWNLOAD_DIR%" mkdir "%DOWNLOAD_DIR%"
if not exist "%OLLAMA_BIN%" mkdir "%OLLAMA_BIN%"
if not exist "%OLLAMA_MODELS%" mkdir "%OLLAMA_MODELS%"
if not exist "%OLLAMA_IMPORTS%" mkdir "%OLLAMA_IMPORTS%"

if exist "%OLLAMA_BIN%\ollama.exe" (
  echo Ollama already exists:
  echo %OLLAMA_BIN%\ollama.exe
  goto done
)

echo Downloading standalone Ollama for Windows...
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%OLLAMA_URL%' -OutFile '%OLLAMA_ZIP%' -UseBasicParsing"
if errorlevel 1 (
  echo.
  echo Failed to download Ollama from:
  echo %OLLAMA_URL%
  echo Check internet access, then run this file again.
  exit /b 1
)

echo Extracting Ollama...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $bin='%OLLAMA_BIN%'; $tmp=Join-Path '%OLLAMA_ROOT%' 'extract_tmp'; if (Test-Path $tmp) { Remove-Item -LiteralPath $tmp -Recurse -Force }; New-Item -ItemType Directory -Path $tmp | Out-Null; Expand-Archive -LiteralPath '%OLLAMA_ZIP%' -DestinationPath $tmp -Force; $exe=Get-ChildItem -LiteralPath $tmp -Recurse -Filter 'ollama.exe' | Select-Object -First 1; if (-not $exe) { throw 'ollama.exe was not found in the downloaded zip.' }; Copy-Item -Path (Join-Path $exe.DirectoryName '*') -Destination $bin -Recurse -Force; Remove-Item -LiteralPath $tmp -Recurse -Force"
if errorlevel 1 (
  echo.
  echo Ollama extraction failed.
  exit /b 1
)

if not exist "%OLLAMA_BIN%\ollama.exe" (
  echo.
  echo Ollama install did not create:
  echo %OLLAMA_BIN%\ollama.exe
  exit /b 1
)

:done
echo.
echo Local Ollama setup complete.
echo Models folder:
echo %OLLAMA_MODELS%
echo.
echo To start the server, run:
echo Win\ollama_server_start.bat
echo.
echo If you have a GGUF model from LM Studio, put it in:
echo %OLLAMA_IMPORTS%
echo Then create a Modelfile and run:
echo .standalone\ollama\bin\ollama.exe create your-model-name -f Modelfile
echo.
endlocal
