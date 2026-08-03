@echo off
setlocal
cd /d "%~dp0"

set PORT=8000
set HOST=127.0.0.1

start "" "http://%HOST%:%PORT%"

".venv\Scripts\python.exe" -m uvicorn app.main:app --host %HOST% --port %PORT%
