@echo off
set CURRENT_DIR=%CD%
set PYTHON_EXE=%CURRENT_DIR%\.venv\Scripts\python.exe

if not exist "%PYTHON_EXE%" (
    echo Python virtual environment not found at %PYTHON_EXE%
    pause
    exit /b 1
)

"%PYTHON_EXE%" -m PyInstaller --onefile --windowed --icon=assets\icon.ico ^
  --add-data "assets;assets" ^
  --hidden-import pydexcom ^
  --hidden-import cryptography ^
  --name Dexfloat Dexfloat.py

pause
