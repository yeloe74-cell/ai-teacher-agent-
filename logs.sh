#!/bin/bash
# logs.sh
# AI Teacher Bot - Universal Log Viewer

echo "========================================"
echo "📜 AI Teacher Bot - Log Viewer"
echo "========================================"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# 1. VPS Systemd Service စစ်ဆေးခြင်း
if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet ai-teacher-bot 2>/dev/null; then
    echo "🟢 Bot Status: RUNNING (systemd service)"
    echo "========================================"
    echo "📜 Systemd Journal Logs (Last 50 lines):"
    echo ""
    journalctl -u ai-teacher-bot -n 50 --no-pager
    exit 0
fi

# 2. File-based Logs စစ်ဆေးခြင်း (JustRunMyApp / Local Direct Run)
echo "ℹ️  Systemd service not active or non-systemd environment."
echo "========================================"
echo "📜 File Logs (logs/app.log):"
echo ""

if [ -f "logs/app.log" ]; then
    tail -n 50 logs/app.log
else
    echo "⚠️ No log file found at logs/app.log"
fi

