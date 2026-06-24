#!/bin/bash
# ============================================================
# Monitor Hermes desde terminal (local o SSH remoto)
# Uso: ./monitor.sh [follow|status|errors|test]
# ============================================================

MODE="${1:-follow}"

case "$MODE" in
    follow|f)
        echo "=== Hermes Live Logs (Ctrl+C to stop) ==="
        journalctl -u hermes-assistant -f --output=short-iso
        ;;
    status|s)
        echo "=== Service Status ==="
        systemctl status hermes-assistant --no-pager
        echo ""
        echo "=== Last 50 log lines ==="
        journalctl -u hermes-assistant -n 50 --no-pager
        ;;
    errors|e)
        echo "=== Errors (last 24h) ==="
        journalctl -u hermes-assistant -p err --since "24 hours ago" --no-pager
        ;;
    test|t)
        echo "=== Testing GPU node connectivity ==="
        VENV="/opt/hermes-assistant/venv"
        BRAIN="/opt/hermes-assistant/brain"
        if [ -d "$VENV" ]; then
            "$VENV/bin/python" "$BRAIN/test_connection.py"
        else
            echo "Hermes not deployed yet. Run scripts/deploy_brain.sh first."
        fi
        ;;
    restart|r)
        sudo systemctl restart hermes-assistant
        echo "Service restarted."
        journalctl -u hermes-assistant -n 20 --no-pager
        ;;
    *)
        echo "Usage: $0 [follow|status|errors|test|restart]"
        echo ""
        echo "  follow  (f) — Stream live logs"
        echo "  status  (s) — Service status + last 50 lines"
        echo "  errors  (e) — Show errors from last 24h"
        echo "  test    (t) — Test GPU node connectivity"
        echo "  restart (r) — Restart the service"
        exit 1
        ;;
esac
