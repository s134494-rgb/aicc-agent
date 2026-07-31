@echo off
title AICC
cd /d "%~dp0"
if not exist "app\data" mkdir "app\data"
if not exist "app\uploads" mkdir "app\uploads"
if not exist ".venv\Scripts\python.exe" (
  py -3.11 -m venv .venv
  call .venv\Scripts\activate
  python -m pip install --upgrade pip
  pip install -r requirements.txt
) else (
  call .venv\Scripts\activate
)
start "" http://127.0.0.1:8000
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
