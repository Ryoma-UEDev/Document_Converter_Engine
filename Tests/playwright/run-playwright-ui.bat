@echo off
setlocal

cd /d "%~dp0"

set "TEMP=%CD%\.tmp"
set "TMP=%TEMP%"
if not exist "%TEMP%" mkdir "%TEMP%"

echo Document Converter Playwright UI
echo.
choice /C YN /N /M "Enable integration tests? [Y/N]: "

if errorlevel 2 (
    set "RUN_INTEGRATION=false"
    echo.
    echo Integration tests disabled. They will show as skipped.
) else (
    set "RUN_INTEGRATION=true"
    echo.
    echo Integration tests enabled.
    echo Default document path: ..\TestDocument.pdf
    echo Use TEST_DOCUMENT before launching this script to override it.
    if defined TEST_DOCUMENT echo TEST_DOCUMENT=%TEST_DOCUMENT%
)

echo.
npx.cmd playwright test --ui
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo Playwright UI exited with code %EXIT_CODE%.
)

exit /b %EXIT_CODE%
