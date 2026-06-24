#!/bin/bash
# ============================================================
# FASE 1 — Configurar hostname estático y mDNS en la Lenovo
# Permite acceder como: lenovo.local desde la red
# Ejecutar EN LA LENOVO con sudo
# ============================================================
set -euo pipefail

HOSTNAME="${1:-hermes-server}"

echo "=== mDNS / Hostname Setup ==="
echo "Hostname: $HOSTNAME"
echo ""

# Instalar avahi (mDNS para Linux)
if ! command -v avahi-daemon &>/dev/null; then
    sudo apt-get update -q
    sudo apt-get install -y avahi-daemon
    echo "[OK] avahi-daemon installed"
fi

# Establecer hostname
sudo hostnamectl set-hostname "$HOSTNAME"

# Asegurar que /etc/hosts incluye el hostname local
if ! grep -q "$HOSTNAME" /etc/hosts; then
    echo "127.0.0.1 $HOSTNAME $HOSTNAME.local" | sudo tee -a /etc/hosts > /dev/null
    echo "[OK] Added $HOSTNAME to /etc/hosts"
fi

# Habilitar y arrancar avahi
sudo systemctl enable avahi-daemon
sudo systemctl restart avahi-daemon

echo "[OK] mDNS active. Lenovo is now reachable as: $HOSTNAME.local"
echo ""
echo "Test from main PC (Windows):"
echo "  ping $HOSTNAME.local"
echo "  ssh usuario@$HOSTNAME.local"
