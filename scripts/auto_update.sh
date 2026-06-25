#!/bin/bash
# Auto-update: chequea si hay cambios en el repo y actualiza Hermes automáticamente.
# Se ejecuta cada 5 minutos via systemd timer o crontab.

REPO_DIR="$HOME/hermes"
BRANCH="master"
LOG_FILE="$REPO_DIR/logs/auto_update.log"
VENV_PIP="$REPO_DIR/venv/bin/pip"
SERVICE_NAME="hermes"

mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

cd "$REPO_DIR" || { log "ERROR: No se puede acceder a $REPO_DIR"; exit 1; }

# Fetch cambios remotos
git fetch origin "$BRANCH" --quiet 2>> "$LOG_FILE"
if [ $? -ne 0 ]; then
    log "ERROR: git fetch falló"
    exit 1
fi

# Comparar HEAD local con remoto
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse "origin/$BRANCH")

if [ "$LOCAL" = "$REMOTE" ]; then
    # No hay cambios, salir silenciosamente
    exit 0
fi

log "Cambios detectados: $LOCAL -> $REMOTE"
log "Commits nuevos:"
git log --oneline "$LOCAL..$REMOTE" >> "$LOG_FILE" 2>&1

# Pull cambios
git pull origin "$BRANCH" --ff-only >> "$LOG_FILE" 2>&1
if [ $? -ne 0 ]; then
    log "ERROR: git pull falló. Puede haber conflictos."
    exit 1
fi

# Instalar dependencias nuevas si requirements.txt cambió
if git diff "$LOCAL..$REMOTE" --name-only | grep -q "requirements.txt"; then
    log "requirements.txt cambió, instalando dependencias..."
    if [ -f "$VENV_PIP" ]; then
        "$VENV_PIP" install -r brain/requirements.txt --quiet >> "$LOG_FILE" 2>&1
    else
        pip install -r brain/requirements.txt --quiet >> "$LOG_FILE" 2>&1
    fi
fi

# Reiniciar Hermes
log "Reiniciando Hermes..."
if systemctl --user is-active "$SERVICE_NAME" > /dev/null 2>&1; then
    systemctl --user restart "$SERVICE_NAME" >> "$LOG_FILE" 2>&1
    log "Hermes reiniciado via systemd (user)"
elif sudo systemctl is-active "$SERVICE_NAME" > /dev/null 2>&1; then
    sudo systemctl restart "$SERVICE_NAME" >> "$LOG_FILE" 2>&1
    log "Hermes reiniciado via systemd (system)"
else
    # Fallback: matar y reiniciar manualmente
    pkill -f "python.*main.py" 2>/dev/null
    sleep 2
    cd "$REPO_DIR/brain"
    nohup python main.py >> "$LOG_FILE" 2>&1 &
    log "Hermes reiniciado manualmente (PID: $!)"
fi

log "Actualización completada exitosamente"
