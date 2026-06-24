# ============================================================
# Instalar WSL2 + Ubuntu en la Lenovo (Windows 10)
# EJECUTAR EN LA LENOVO como Administrador
# ============================================================

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Instalacion de WSL2 + Ubuntu en Lenovo" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# 1. Verificar version de Windows
$build = [System.Environment]::OSVersion.Version.Build
Write-Host "Windows build detectado: $build"

if ($build -lt 19041) {
    Write-Host ""
    Write-Host "[!] Tu Windows 10 es demasiado antiguo para WSL2 automatico." -ForegroundColor Yellow
    Write-Host "    Necesitas actualizar Windows 10 primero." -ForegroundColor Yellow
    Write-Host "    Ve a: Configuracion > Windows Update > Buscar actualizaciones" -ForegroundColor Yellow
    exit 1
}

# 2. Habilitar WSL y plataforma de maquina virtual
Write-Host ""
Write-Host "[1/4] Habilitando WSL..." -ForegroundColor Yellow
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart | Out-Null

Write-Host "[2/4] Habilitando Maquina Virtual (necesario para WSL2)..." -ForegroundColor Yellow
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart | Out-Null

# 3. Descargar kernel de WSL2
Write-Host "[3/4] Descargando actualizacion del kernel de Linux..." -ForegroundColor Yellow
$kernelUrl  = "https://wslstorestorage.blob.core.windows.net/wslblob/wsl_update_x64.msi"
$kernelPath = "$env:TEMP\wsl_update_x64.msi"
$ProgressPreference = 'SilentlyContinue'
Invoke-WebRequest -Uri $kernelUrl -OutFile $kernelPath -UseBasicParsing
Start-Process msiexec.exe -ArgumentList "/i `"$kernelPath`" /quiet /norestart" -Wait
Write-Host "     Kernel instalado." -ForegroundColor Green

# 4. Configurar WSL2 como version por defecto
Write-Host "[4/4] Configurando WSL2 como version por defecto..." -ForegroundColor Yellow
wsl --set-default-version 2

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Base de WSL2 lista!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "SIGUIENTE PASO:" -ForegroundColor Cyan
Write-Host "  1. Reinicia la Lenovo ahora" -ForegroundColor White
Write-Host "  2. Despues del reinicio, abre PowerShell y ejecuta:" -ForegroundColor White
Write-Host "     wsl --install -d Ubuntu" -ForegroundColor Yellow
Write-Host "  3. Cuando te pida nombre de usuario, pon algo simple como 'cris'" -ForegroundColor White
Write-Host "  4. Pon una contrasena que recuerdes" -ForegroundColor White
Write-Host ""
