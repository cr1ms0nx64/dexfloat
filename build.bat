@echo off
setlocal
cd /d "%~dp0"
set "DEXFLOAT_PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%DEXFLOAT_PYTHON%" (
    echo Die virtuelle Python-Umgebung fehlt. Bitte zuerst das Entwickler-Setup aus der README ausfuehren.
    exit /b 1
)
"%DEXFLOAT_PYTHON%" -m PyInstaller --noconfirm --clean Dexfloat.spec
exit /b %ERRORLEVEL%
