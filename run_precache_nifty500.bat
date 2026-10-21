@echo off
echo ==============================================================
echo Pre-Caching Historical Data for Nifty 500 Stocks
echo Date Range: 01-Jan-2019 to Yesterday
echo Target DB:  data\price_cache.db
echo ==============================================================

set "PYTHON_EXE=%~dp0..\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=%~dp0..\..\.venv\Scripts\python.exe"
)
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=python"
)

"%PYTHON_EXE%" precache_nifty500.py %*
pause
