@echo off
echo ==============================================================
echo Purging BAGMANE and DUMMYHEG from price_cache.db
echo ==============================================================

set "PYTHON_EXE=%~dp0..\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=%~dp0..\..\.venv\Scripts\python.exe"
)
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=python"
)

"%PYTHON_EXE%" remove_excluded_stocks.py
echo.
pause
