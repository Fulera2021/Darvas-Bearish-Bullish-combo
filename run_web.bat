@echo off
echo ==============================================================
echo Starting Darvas Bearish + Bullish Combo Web Application
echo URL: http://localhost:8005
echo ==============================================================
"C:\Users\krish\Desktop\API\Anti Gravity\.venv\Scripts\python.exe" -m uvicorn web.app:app --host 0.0.0.0 --port 8005 --reload
pause
