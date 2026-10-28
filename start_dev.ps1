# StoreFlow AI 2.0 - One-Click Launcher for PowerShell
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  StoreFlow AI 2.0 - Starting All Services..." -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Ollama Service
Start-Process powershell -ArgumentList "-NoExit", "-Command", "ollama serve"

# 2. Backend FastAPI
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

# 3. Frontend Vite
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; npm run dev"

Write-Host "`nAll 3 services launched successfully in separate windows!" -ForegroundColor Green
Write-Host "Frontend:        http://localhost:5173" -ForegroundColor Yellow
Write-Host "Backend API:     http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host "Ollama Engine:   http://localhost:11434" -ForegroundColor Yellow

