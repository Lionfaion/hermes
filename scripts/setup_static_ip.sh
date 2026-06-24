#!/bin/bash
# ============================================================
# FASE 1 — IP estática en la Lenovo (Ubuntu/Debian con netplan)
# Alternativa a mDNS para entornos donde .local no funciona
# Ejecutar EN LA LENOVO con sudo
# ============================================================
set -euo pipefail

STATIC_IP="${1:-192.168.1.50}"
GATEWAY="${2:-192.168.1.1}"
DNS="${3:-8.8.8.8}"

echo "=== Static IP Configuration ==="

# Detectar interfaz de red activa
INTERFACE=$(ip route | grep default | awk '{print $5}' | head -1)

if [ -z "$INTERFACE" ]; then
    echo "Available interfaces:"
    ip -br link show | grep -v lo
    echo ""
    read -rp "Enter interface name (e.g., eth0, enp3s0): " INTERFACE
fi

echo "Interface : $INTERFACE"
echo "Static IP : $STATIC_IP/24"
echo "Gateway   : $GATEWAY"
echo ""
read -rp "Apply this configuration? [y/N]: " CONFIRM
[[ "$CONFIRM" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }

# Hacer backup de netplan existente
sudo cp -r /etc/netplan /etc/netplan.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null || true

# Escribir configuración netplan
sudo tee /etc/netplan/99-hermes-static.yaml > /dev/null << EOF
network:
  version: 2
  renderer: networkd
  ethernets:
    $INTERFACE:
      dhcp4: no
      addresses: [$STATIC_IP/24]
      routes:
        - to: default
          via: $GATEWAY
      nameservers:
        addresses: [$DNS, 8.8.4.4]
EOF

sudo chmod 600 /etc/netplan/99-hermes-static.yaml
sudo netplan apply

echo ""
echo "[OK] Static IP configured: $STATIC_IP"
echo "     Reconnect via: ssh usuario@$STATIC_IP"
