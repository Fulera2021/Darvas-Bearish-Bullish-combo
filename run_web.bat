@echo off
echo ==============================================================
echo Starting Darvas Bearish + Bullish Combo Web Application
echo URL: http://localhost:8005
echo ==============================================================
set "PYTHON_EXE=%~dp0..\..\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=python"
)
"%PYTHON_EXE%" -m uvicorn web.app:app --host 0.0.0.0 --port 8005 --reload
pause
