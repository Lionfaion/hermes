# Script maestro de despliegue de Hermes v2
# Ejecutar en la PC PRINCIPAL para transferir todo a la Lenovo via SCP
# Prerequisito: SSH activo y clave configurada

param(
    [string]$Host = "192.168.0.182",
    [string]$User = "chsan",
    [string]$KeyFile = "C:\Users\Cris\.ssh\hermes_key"
)

$SSH_DEST = "${User}@${Host}"
$BRAIN_LOCAL = "C:\Users\Cris\hermes-assistant\brain"
$BRAIN_REMOTE = "C:\Users\chsan\hermes-assistant\brain"
$SCRIPTS_LOCAL = "C:\Users\Cris\hermes-assistant\scripts"

Write-Host "=== Desplegando Hermes v2 en $SSH_DEST ===" -ForegroundColor Cyan

# ── Crear directorios remotos ──────────────────────────────────────────────────
Write-Host "`n[1/4] Creando estructura de directorios..." -ForegroundColor Yellow
$dirs = @(
    "$BRAIN_REMOTE\rag",
    "$BRAIN_REMOTE\learning",
    "C:\Users\chsan\hermes-assistant\logs\interacciones"
)
foreach ($d in $dirs) {
    $escaped = $d.Replace("\", "\\")
    ssh -i $KeyFile -o StrictHostKeyChecking=no $SSH_DEST "powershell -Command `"New-Item -ItemType Directory -Force -Path '$d'`""
}

# ── Transferir archivos del brain ──────────────────────────────────────────────
Write-Host "`n[2/4] Transfiriendo archivos..." -ForegroundColor Yellow

$files = @(
    "config.py",
    "assistant.py",
    "rag\__init__.py",
    "rag\indexer.py",
    "rag\searcher.py",
    "learning\__init__.py",
    "learning\logger.py",
    "learning\skills_manager.py",
    "learning\reflexion_diaria.py",
    "learning\debate_sintetico.py"
)

foreach ($f in $files) {
    $local_path = "$BRAIN_LOCAL\$f"
    $remote_dir = "$BRAIN_REMOTE\" + (Split-Path $f -Parent)
    $remote_dir_escaped = $remote_dir.Replace("\", "\\")

    # SCP necesita forward slashes y formato especial para Windows
    $local_scp = $local_path.Replace("\", "/")
    $remote_scp = "${SSH_DEST}:" + $remote_dir.Replace("\", "\\")

    Write-Host "  -> $f"
    scp -i $KeyFile -o StrictHostKeyChecking=no "$local_path" "${SSH_DEST}:${remote_dir_escaped}"
}

# ── Instalar dependencias nuevas ───────────────────────────────────────────────
Write-Host "`n[3/4] Instalando dependencias nuevas en Lenovo..." -ForegroundColor Yellow
Write-Host "  (sentence-transformers descarga ~500MB la primera vez, puede demorar)" -ForegroundColor DarkYellow

$PIP_REMOTE = "C:\Users\chsan\hermes-python\Scripts\pip.exe"
ssh -i $KeyFile $SSH_DEST "& '$PIP_REMOTE' install pyyaml chromadb sentence-transformers --no-warn-script-location"

# ── Crear vault ────────────────────────────────────────────────────────────────
Write-Host "`n[4/4] Creando vault de notas..." -ForegroundColor Yellow
scp -i $KeyFile "$SCRIPTS_LOCAL\crear_vault.ps1" "${SSH_DEST}:C:\Users\chsan\crear_vault.ps1"
ssh -i $KeyFile $SSH_DEST "powershell -ExecutionPolicy Bypass -File C:\Users\chsan\crear_vault.ps1"

Write-Host "`n=== Despliegue completado ===" -ForegroundColor Green
Write-Host "Ahora en la Lenovo, reinicia Hermes:"
Write-Host "  ssh -i $KeyFile $SSH_DEST"
Write-Host "  Stop-Process -Name python -Force"
Write-Host "  Start-Process 'C:\Users\chsan\hermes-assistant\start_hermes.bat'"
Write-Host ""
Write-Host "Para registrar tareas nocturnas (como Admin en la Lenovo):"
Write-Host "  scp -i $KeyFile '$SCRIPTS_LOCAL\registrar_tareas_v2.ps1' ${SSH_DEST}:C:\Users\chsan\"
Write-Host "  (abrir PowerShell Admin en Lenovo y ejecutar: C:\Users\chsan\registrar_tareas_v2.ps1)"
