# Registra las tareas nocturnas de Hermes en el Programador de Tareas de Windows
# Ejecutar en la Lenovo como Administrador

$PYTHON = "C:\Users\chsan\hermes-python\python.exe"
$BRAIN  = "C:\Users\chsan\hermes-assistant\brain"
$LOGS   = "C:\Users\chsan\hermes-assistant\logs"

New-Item -ItemType Directory -Force -Path $LOGS | Out-Null

Write-Host "=== Registrando tareas nocturnas de Hermes ===" -ForegroundColor Cyan

# ── Tarea 1: Indexar vault (cada 6 horas) ─────────────────────────────────────
$idx_script = @"
import sys
from pathlib import Path
sys.path.insert(0, r'$BRAIN')
from rag.indexer import VaultIndexer
from config import VAULT_PATH, CHROMA_PATH
idx = VaultIndexer(VAULT_PATH, CHROMA_PATH)
n = idx.index_vault()
print(f'Indexados {n} fragmentos del vault.')
"@

$idx_path = "C:\Users\chsan\hermes-assistant\run_indexar.py"
$idx_script | Out-File -FilePath $idx_path -Encoding UTF8

$taskAction1 = New-ScheduledTaskAction `
    -Execute $PYTHON `
    -Argument $idx_path `
    -WorkingDirectory $BRAIN

$taskTrigger1 = @(
    $(New-ScheduledTaskTrigger -Daily -At "08:00AM"),
    $(New-ScheduledTaskTrigger -Daily -At "02:00PM"),
    $(New-ScheduledTaskTrigger -Daily -At "08:00PM")
)

$taskSettings1 = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName "Hermes - Indexar Vault" `
    -Action $taskAction1 `
    -Trigger $taskTrigger1 `
    -Settings $taskSettings1 `
    -RunLevel Limited `
    -Force | Out-Null

Write-Host "OK - Tarea 'Indexar Vault' registrada (08:00 / 14:00 / 20:00)" -ForegroundColor Green

# ── Tarea 2: Reflexión nocturna (3:00 AM) ─────────────────────────────────────
$taskAction2 = New-ScheduledTaskAction `
    -Execute $PYTHON `
    -Argument "C:\Users\chsan\hermes-assistant\brain\learning\reflexion_diaria.py" `
    -WorkingDirectory $BRAIN

$taskTrigger2 = New-ScheduledTaskTrigger -Daily -At "03:00AM"

$taskSettings2 = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 20) `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName "Hermes - Reflexion Nocturna" `
    -Action $taskAction2 `
    -Trigger $taskTrigger2 `
    -Settings $taskSettings2 `
    -RunLevel Limited `
    -Force | Out-Null

Write-Host "OK - Tarea 'Reflexion Nocturna' registrada (03:00 AM)" -ForegroundColor Green

# ── Tarea 3: Debate sintético (4:00 AM) ───────────────────────────────────────
$taskAction3 = New-ScheduledTaskAction `
    -Execute $PYTHON `
    -Argument "C:\Users\chsan\hermes-assistant\brain\learning\debate_sintetico.py" `
    -WorkingDirectory $BRAIN

$taskTrigger3 = New-ScheduledTaskTrigger -Daily -At "04:00AM"

$taskSettings3 = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName "Hermes - Debate Sintetico" `
    -Action $taskAction3 `
    -Trigger $taskTrigger3 `
    -Settings $taskSettings3 `
    -RunLevel Limited `
    -Force | Out-Null

Write-Host "OK - Tarea 'Debate Sintetico' registrada (04:00 AM)" -ForegroundColor Green

Write-Host "`n=== Todas las tareas registradas ===" -ForegroundColor Cyan
Write-Host "Horario nocturno de Hermes:"
Write-Host "  03:00 AM - Reflexion: analiza conversaciones del dia, actualiza skills.yaml"
Write-Host "  04:00 AM - Debate: genera conocimiento sintetico, guarda en vault"
Write-Host "  08:00 AM, 14:00, 20:00 - Indexar: actualiza busqueda semantica del vault"
