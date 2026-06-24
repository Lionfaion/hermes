# ============================================================
# FASE 1 — Generar par de claves SSH y configurar acceso a Lenovo
# Ejecutar en la PC PRINCIPAL (Windows)
# ============================================================
param(
    [string]$LenovoUser = "tu_usuario",
    [string]$LenovoHost = "192.168.1.50",   # IP o hostname.local de la Lenovo
    [string]$KeyName    = "hermes_key"
)

$KeyPath = "$env:USERPROFILE\.ssh\$KeyName"

Write-Host "=== SSH Key Setup for Hermes ===" -ForegroundColor Cyan
Write-Host "Target: $LenovoUser@$LenovoHost"
Write-Host ""

# Crear directorio .ssh si no existe
if (-not (Test-Path "$env:USERPROFILE\.ssh")) {
    New-Item -ItemType Directory -Path "$env:USERPROFILE\.ssh" | Out-Null
}

# Generar clave Ed25519 (más moderna y segura que RSA)
if (-not (Test-Path $KeyPath)) {
    ssh-keygen -t ed25519 -C "hermes-assistant@$env:COMPUTERNAME" -f $KeyPath -N '""'
    Write-Host "[OK] Key pair created at $KeyPath" -ForegroundColor Green
} else {
    Write-Host "[--] Key already exists at $KeyPath" -ForegroundColor Yellow
}

$pubKey = Get-Content "$KeyPath.pub"
Write-Host ""
Write-Host "Public key to add on Lenovo (~/.ssh/authorized_keys):" -ForegroundColor Cyan
Write-Host $pubKey -ForegroundColor Gray
Write-Host ""

# Copiar clave al servidor si ssh-copy-id está disponible (Git Bash / WSL)
Write-Host "--- Option A: Automatic (requires password once) ---" -ForegroundColor Yellow
Write-Host "  Run in Git Bash or WSL:"
Write-Host "  ssh-copy-id -i `"$KeyPath.pub`" $LenovoUser@$LenovoHost"
Write-Host ""

Write-Host "--- Option B: Manual ---" -ForegroundColor Yellow
Write-Host "  1. SSH into the Lenovo with password:"
Write-Host "     ssh $LenovoUser@$LenovoHost"
Write-Host "  2. On the Lenovo, run:"
Write-Host "     mkdir -p ~/.ssh && chmod 700 ~/.ssh"
Write-Host "     echo '$pubKey' >> ~/.ssh/authorized_keys"
Write-Host "     chmod 600 ~/.ssh/authorized_keys"
Write-Host ""

Write-Host "--- Test key-based login ---" -ForegroundColor Yellow
Write-Host "  ssh -i `"$KeyPath`" $LenovoUser@$LenovoHost"
Write-Host ""

# Crear entrada en ~/.ssh/config para comodidad
$sshConfig = "$env:USERPROFILE\.ssh\config"
$configEntry = @"

Host lenovo hermes-server
    HostName $LenovoHost
    User $LenovoUser
    IdentityFile $KeyPath
    ServerAliveInterval 60
"@

$existingConfig = if (Test-Path $sshConfig) { Get-Content $sshConfig -Raw } else { "" }
if ($existingConfig -notmatch "hermes-server") {
    Add-Content -Path $sshConfig -Value $configEntry
    Write-Host "[OK] SSH config alias added — you can now use: ssh lenovo" -ForegroundColor Green
} else {
    Write-Host "[--] SSH config entry already exists" -ForegroundColor Yellow
}
