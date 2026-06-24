#!/bin/bash
# ============================================================
# FASE 3 + 4 — Deploy Hermes Brain en la Lenovo (Linux Server)
# Ejecutar EN LA LENOVO como usuario con sudo
# Prerequisito: Python 3.10+, git opcional
# ============================================================
set -euo pipefail

INSTALL_DIR="/opt/hermes-assistant"
VENV_DIR="$INSTALL_DIR/venv"
SERVICE_USER="hermes"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "==========================================="
echo "  Hermes Brain Deployment"
echo "  Source : $SOURCE_DIR"
echo "  Target : $INSTALL_DIR"
echo "==========================================="
echo ""

# --- 1. Crear usuario de sistema para el servicio ---
if ! id "$SERVICE_USER" &>/dev/null; then
    sudo useradd --system --no-create-home --shell /bin/false "$SERVICE_USER"
    echo "[OK] System user created: $SERVICE_USER"
else
    echo "[--] User '$SERVICE_USER' already exists"
fi

# --- 2. Crear estructura de directorios ---
sudo mkdir -p "$INSTALL_DIR/brain/data"
sudo mkdir -p "$INSTALL_DIR/brain/interface"
echo "[OK] Directories ready"

# --- 3. Copiar archivos del brain ---
sudo cp -r "$SOURCE_DIR/brain/"* "$INSTALL_DIR/brain/"
echo "[OK] Brain files deployed"

# --- 4. Entorno virtual Python ---
if [ ! -d "$VENV_DIR" ]; then
    sudo python3 -m venv "$VENV_DIR"
    echo "[OK] Virtual environment created"
fi
sudo "$VENV_DIR/bin/pip" install --quiet --upgrade pip
sudo "$VENV_DIR/bin/pip" install --quiet -r "$INSTALL_DIR/brain/requirements.txt"
echo "[OK] Python dependencies installed"

# --- 5. Configuración (.env) ---
if [ ! -f "$INSTALL_DIR/brain/.env" ]; then
    sudo cp "$INSTALL_DIR/brain/.env.example" "$INSTALL_DIR/brain/.env"
    echo ""
    echo "[!] IMPORTANT: edit the .env file before starting the service:"
    echo "    sudo nano $INSTALL_DIR/brain/.env"
    echo "    (set GPU_NODE_HOST to your main PC's local IP)"
    echo ""
else
    echo "[--] .env already exists, skipping"
fi

# --- 6. Permisos ---
sudo chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
sudo chmod 750 "$INSTALL_DIR/brain"
sudo chmod 770 "$INSTALL_DIR/brain/data"
echo "[OK] Permissions set"

# --- 7. Servicio systemd ---
sudo cp "$SOURCE_DIR/systemd/hermes-assistant.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable hermes-assistant.service
echo "[OK] systemd service installed and enabled"

echo ""
echo "==========================================="
echo "  Deployment complete!"
echo "==========================================="
echo ""
echo "  Next steps:"
echo "  1. Edit config  : sudo nano $INSTALL_DIR/brain/.env"
echo "  2. Start service: sudo systemctl start hermes-assistant"
echo "  3. Check status : sudo systemctl status hermes-assistant"
echo "  4. Follow logs  : sudo journalctl -u hermes-assistant -f"
echo ""
echo "  Interactive CLI (via SSH):"
echo "  $VENV_DIR/bin/python $INSTALL_DIR/brain/interface/cli.py"
echo ""
