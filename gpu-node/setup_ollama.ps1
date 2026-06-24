# ============================================================
# FASE 2 — Configurar Ollama para acceso desde red local
# Ejecutar en la PC PRINCIPAL (Windows) como Administrador
# ============================================================

Write-Host "=== Ollama LAN Configuration ===" -ForegroundColor Cyan

# 1. Variable de entorno a nivel de sistema
[System.Environment]::SetEnvironmentVariable("OLLAMA_HOST", "0.0.0.0:11434", "Machine")
Write-Host "[OK] OLLAMA_HOST = 0.0.0.0:11434 (system-wide)" -ForegroundColor Green

# 2. Regla de firewall para permitir conexiones entrantes en puerto 11434
$ruleName = "Ollama LAN API"
$existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if (-not $existing) {
    try {
        New-NetFirewallRule `
            -DisplayName  $ruleName `
            -Direction    Inbound `
            -Protocol     TCP `
            -LocalPort    11434 `
            -Action       Allow | Out-Null
        Write-Host "[OK] Firewall rule created for TCP 11434" -ForegroundColor Green
    } catch {
        Write-Warning "Could not create firewall rule automatically. Add it manually in Windows Defender Firewall."
    }
} else {
    Write-Host "[--] Firewall rule already exists" -ForegroundColor Yellow
}

# 3. Detectar IP local
$ip = (Get-NetIPAddress -AddressFamily IPv4 |
       Where-Object { $_.InterfaceAlias -notmatch "Loopback" -and
                      $_.IPAddress -notmatch "^169" } |
       Select-Object -First 1).IPAddress

Write-Host ""
Write-Host "Main PC local IP : $ip" -ForegroundColor Yellow
Write-Host "Set this in the Lenovo's .env :" -ForegroundColor Yellow
Write-Host "  GPU_NODE_HOST=$ip" -ForegroundColor White
Write-Host ""
Write-Host "Restart Ollama for changes to take effect:" -ForegroundColor Cyan
Write-Host "  1. Right-click Ollama icon in system tray → Quit"
Write-Host "  2. Reopen Ollama from Start Menu"
Write-Host ""
Write-Host "Verify with:" -ForegroundColor Cyan
Write-Host "  Invoke-RestMethod http://localhost:11434/api/tags"
