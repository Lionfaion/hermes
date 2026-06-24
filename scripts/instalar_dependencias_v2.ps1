# Instala las dependencias nuevas (RAG + aprendizaje) en Python embeddable de la Lenovo
# Ejecutar en la Lenovo como usuario chsan

$PIP = "C:\Users\chsan\hermes-python\Scripts\pip.exe"

Write-Host "=== Instalando dependencias de Hermes v2 (RAG + Autoaprendizaje) ===" -ForegroundColor Cyan

$paquetes = @(
    "pyyaml>=6.0",
    "sentence-transformers>=2.2.2",
    "chromadb>=0.4.0"
)

foreach ($pkg in $paquetes) {
    Write-Host "`nInstalando: $pkg" -ForegroundColor Yellow
    & $PIP install $pkg --no-warn-script-location
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR instalando $pkg" -ForegroundColor Red
        exit 1
    }
}

Write-Host "`n=== Instalacion completada ===" -ForegroundColor Green
Write-Host "Verificando importaciones..." -ForegroundColor Cyan

$PYTHON = "C:\Users\chsan\hermes-python\python.exe"
& $PYTHON -c "import yaml; import chromadb; from sentence_transformers import SentenceTransformer; print('OK - todas las dependencias funcionan')"

if ($LASTEXITCODE -eq 0) {
    Write-Host "Listo! Hermes v2 puede arrancar." -ForegroundColor Green
} else {
    Write-Host "Hay errores. Revisa los mensajes de arriba." -ForegroundColor Red
}
