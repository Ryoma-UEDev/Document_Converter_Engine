@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

set "OLLAMA_ROOT=%CD%\.standalone\ollama"
set "OLLAMA_BIN=%OLLAMA_ROOT%\bin"
set "OLLAMA_MODELS=%OLLAMA_ROOT%\models"
set "OLLAMA_IMPORTS=%OLLAMA_ROOT%\imports"
set "OLLAMA_HOST=127.0.0.1:11434"

if not exist "%OLLAMA_BIN%\ollama.exe" (
  echo Local Ollama was not found.
  echo Run setup_ollama_standalone.bat first.
  exit /b 1
)

if not exist "%OLLAMA_MODELS%" mkdir "%OLLAMA_MODELS%"
if not exist "%OLLAMA_IMPORTS%" mkdir "%OLLAMA_IMPORTS%"

echo.
echo Starting local Ollama server
echo ----------------------------
echo API:
echo http://%OLLAMA_HOST%/v1
echo.
echo Models folder:
echo %OLLAMA_MODELS%
echo.
echo GGUF import/drop folder:
echo %OLLAMA_IMPORTS%
echo.
echo In Document Converter settings use:
echo Ollama Base URL: http://localhost:11434/v1
echo.
echo Press Ctrl+C to stop the Ollama server.
echo.

"%OLLAMA_BIN%\ollama.exe" serve
endlocal
