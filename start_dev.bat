@echo off
title StoreFlow AI - All-in-One Launcher
echo ============================================================
echo   StoreFlow AI 2.0 - Khoi dong toan bo he thong
echo ============================================================

echo [1/3] Khoi dong Ollama Local AI...
start "StoreFlow AI - Ollama" cmd /k "set "OLLAMA_MODELS=D:\Ollama\models" && "D:\Ollama\ollama.exe" serve"

echo [2/3] Khoi dong Backend FastAPI...
start "StoreFlow AI - Backend" cmd /k "cd backend && .venv\Scripts\activate && uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

echo [3/3] Khoi dong Frontend Vite...
start "StoreFlow AI - Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo ============================================================
echo   He thong da duoc khoi chay tren 3 cua so rieng biet!
echo   - Frontend:        http://localhost:5173
echo   - Backend Swagger: http://localhost:8000/docs
echo   - Ollama AI:       http://localhost:11434
echo ============================================================

