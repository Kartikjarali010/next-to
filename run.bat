@echo off
REM Builds the React app and starts the API + web app on http://localhost:8000 (also reachable from a phone on the same Wi-Fi)
cd /d "%~dp0frontend" && call npm install --no-audit --no-fund && call npm run build
cd /d "%~dp0backend" && pip install -r requirements.txt && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
