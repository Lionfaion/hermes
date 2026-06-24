# ============================================================
# Script todo-en-uno para preparar la Lenovo
# PEGAR EN POWERSHELL COMO ADMINISTRADOR en la Lenovo
# ============================================================

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  Preparacion inicial de la Lenovo" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# --- 1. Instalar y arrancar el servidor SSH de Windows ---
Write-Host "[1/5] Instalando servidor SSH..." -ForegroundColor Yellow
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0 | Out-Null
Set-Service -Name sshd -StartupType Automatic
Start-Service sshd
Write-Host "      SSH activo." -ForegroundColor Green

# --- 2. Agregar clave publica de la PC principal ---
Write-Host "[2/5] Configurando acceso SSH con clave segura..." -ForegroundColor Yellow
$pubKey  = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEg71x/D5Z5NqWjJWH+gqscR+l+0GmelrsSKWytRtzW8 hermes@main-pc"
$keyFile = "C:\ProgramData\ssh\administrators_authorized_keys"
New-Item -Force -ItemType File -Path $keyFile | Out-Null
Set-Content -Path $keyFile -Value $pubKey -Encoding utf8

# Permisos requeridos por Windows SSH
icacls $keyFile /inheritance:r | Out-Null
icacls $keyFile /grant "SYSTEM:(F)" | Out-Null
icacls $keyFile /grant "BUILTIN\Administrators:(F)" | Out-Null
Write-Host "      Clave autorizada." -ForegroundColor Green

# --- 3. Habilitar WSL2 ---
Write-Host "[3/5] Habilitando WSL2..." -ForegroundColor Yellow
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart | Out-Null
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart | Out-Null
Write-Host "      WSL2 habilitado." -ForegroundColor Green

# --- 4. Configurar PowerShell como shell SSH por defecto ---
Write-Host "[4/5] Configurando shell SSH..." -ForegroundColor Yellow
New-ItemProperty -Path "HKLM:\SOFTWARE\OpenSSH" `
    -Name DefaultShell `
    -Value "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" `
    -PropertyType String -Force | Out-Null
Write-Host "      Shell configurado." -ForegroundColor Green

# --- 5. Mostrar IP local para que la anotes ---
Write-Host "[5/5] Detectando IP de esta Lenovo..." -ForegroundColor Yellow
$ip = (Get-NetIPAddress -AddressFamily IPv4 |
       Where-Object { $_.InterfaceAlias -notmatch "Loopback" -and
                      $_.IPAddress -notmatch "^169" } |
       Select-Object -First 1).IPAddress
Write-Host "      IP detectada: $ip" -ForegroundColor Green

Write-Host ""
Write-Host "=========================================" -ForegroundColor Green
Write-Host "  LISTO. Ahora:" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  1. ANOTA esta IP: $ip" -ForegroundColor Yellow
Write-Host "  2. Reinicia la Lenovo:" -ForegroundColor White
Write-Host "     Restart-Computer" -ForegroundColor Cyan
Write-Host "  3. Despues del reinicio, abre PowerShell como Admin y ejecuta:" -ForegroundColor White
Write-Host "     wsl --install -d Ubuntu" -ForegroundColor Cyan
Write-Host "  4. Cuando pida usuario: pon un nombre simple (ej: cris)" -ForegroundColor White
Write-Host "  5. Cuando pida contrasena: pon una que recuerdes" -ForegroundColor White
Write-Host "  6. Dile a Claude la IP ($ip), el usuario y la contrasena de Ubuntu" -ForegroundColor White
Write-Host ""
