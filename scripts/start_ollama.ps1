# StoreFlow AI - Local Ollama Service PowerShell Launcher
$env:OLLAMA_MODELS = "D:\Ollama\models"
$env:OLLAMA_HOST = "127.0.0.1:11434"
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  StoreFlow AI - Local Ollama Service Launcher" -ForegroundColor Green
Write-Host "  Models Directory : $env:OLLAMA_MODELS" -ForegroundColor Yellow
Write-Host "  Endpoint         : http://$env:OLLAMA_HOST" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan

if (Test-Path "D:\Ollama\ollama.exe") {
    & "D:\Ollama\ollama.exe" serve
} else {
    Write-Host "[ERROR] Cannot find D:\Ollama\ollama.exe! Please check installation." -ForegroundColor Red
}
