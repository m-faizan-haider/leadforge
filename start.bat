@echo off
title LeadForge AI - Launcher
color 0A

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║          LeadForge AI - Starting Up          ║
echo  ╚══════════════════════════════════════════════╝
echo.

:: ── Check if venv exists ──────────────────────────────
if not exist "venv\Scripts\python.exe" (
    echo  [ERROR] Virtual environment not found!
    echo  Please run: python -m venv venv  ^&^&  venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

:: ── Check if frontend node_modules exists ────────────
if not exist "frontend\node_modules" (
    echo  [INFO] Installing frontend dependencies...
    cd frontend
    call npm install
    cd ..
)

echo  [1/3] Starting FastAPI Backend on http://localhost:8000 ...
start "LeadForge - Backend API" cmd /k "title LeadForge Backend && cd /d %~dp0 && venv\Scripts\python.exe -m uvicorn api.server:app --reload --port 8000"

echo  [2/3] Waiting for backend to boot...
ping -n 5 127.0.0.1 > nul

echo  [3/3] Starting Next.js Frontend on http://localhost:3000 ...
start "LeadForge - Frontend" cmd /k "title LeadForge Frontend && cd /d %~dp0\frontend && npm run dev"

echo  Waiting for frontend to compile...
ping -n 8 127.0.0.1 > nul

echo  Opening browser...
start "" http://localhost:3000

echo.
echo  ================================================================
echo   LeadForge AI is RUNNING!
echo  ================================================================
echo   Dashboard  --^>  http://localhost:3000
echo   API Docs   --^>  http://localhost:8000/docs
echo  ================================================================
echo.
echo  NOTE: Two black terminal windows opened for Backend and Frontend.
echo  To STOP LeadForge, close those two terminal windows.
echo.
pause
