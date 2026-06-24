# ============================================================
# FASE 2 — Descargar modelo de IA optimizado para inferencia local
# Ejecutar en la PC PRINCIPAL (Windows)
# ============================================================
param(
    [string]$Model = "qwen2.5:7b"
)

Write-Host "=== Pulling Ollama Model ===" -ForegroundColor Cyan
Write-Host "Model: $Model"
Write-Host ""

if (-not (Get-Command "ollama" -ErrorAction SilentlyContinue)) {
    Write-Error "Ollama not found. Install it from https://ollama.com/download"
    exit 1
}

# Check if already downloaded
$existing = ollama list 2>$null | Select-String $Model
if ($existing) {
    Write-Host "[--] Model '$Model' already present" -ForegroundColor Yellow
} else {
    Write-Host "Downloading $Model (this may take several minutes)..."
    ollama pull $Model
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to pull $Model"
        exit 1
    }
}

Write-Host ""
Write-Host "[OK] Model '$Model' is ready" -ForegroundColor Green
Write-Host "Test it interactively : ollama run $Model"
Write-Host "Or run api test       : python gpu-node\test_api.py"
