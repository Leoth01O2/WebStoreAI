@echo off
set OLLAMA_MODELS=D:\Ollama\models
set OLLAMA_HOST=127.0.0.1:11434
echo ============================================================
echo   StoreFlow AI - Local Ollama Service Launcher
echo   Models Directory : %OLLAMA_MODELS%
echo   Endpoint         : http://%OLLAMA_HOST%
echo ============================================================
if exist "D:\Ollama\ollama.exe" (
    "D:\Ollama\ollama.exe" serve
) else (
    echo [ERROR] Cannot find D:\Ollama\ollama.exe! Please check installation.
    pause
)
