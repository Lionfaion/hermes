#!/bin/bash
# Script de instalación: configura Hermes como servicio + auto-update.
# Ejecutar UNA SOLA VEZ en la PC local.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Configurando Hermes ==="

# 1. Crear directorio de logs
mkdir -p "$REPO_DIR/logs"

# 2. Hacer ejecutable el script de update
chmod +x "$SCRIPT_DIR/auto_update.sh"

# 3. Crear venv si no existe
if [ ! -d "$REPO_DIR/venv" ]; then
    echo "Creando entorno virtual..."
    python3 -m venv "$REPO_DIR/venv"
    "$REPO_DIR/venv/bin/pip" install -r "$REPO_DIR/brain/requirements.txt"
fi

# 4. Configurar systemd (user-level, no necesita sudo)
mkdir -p "$HOME/.config/systemd/user"

cp "$SCRIPT_DIR/hermes.service" "$HOME/.config/systemd/user/"
cp "$SCRIPT_DIR/hermes-updater.service" "$HOME/.config/systemd/user/"
cp "$SCRIPT_DIR/hermes-updater.timer" "$HOME/.config/systemd/user/"

# 5. Habilitar servicios
systemctl --user daemon-reload
systemctl --user enable hermes.service
systemctl --user enable hermes-updater.timer

# 6. Iniciar todo
systemctl --user start hermes.service
systemctl --user start hermes-updater.timer

# 7. Permitir que los servicios corran sin sesión activa
loginctl enable-linger "$(whoami)" 2>/dev/null || true

echo ""
echo "=== Hermes configurado ==="
echo "Servicio:     systemctl --user status hermes"
echo "Auto-update:  systemctl --user status hermes-updater.timer"
echo "Logs:         tail -f $REPO_DIR/logs/hermes.log"
echo "Update logs:  tail -f $REPO_DIR/logs/auto_update.log"
echo ""
echo "Hermes se actualizará automáticamente cada 5 minutos"
echo "cuando pushees cambios al repo desde Claude Code."
