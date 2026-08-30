#!/bin/bash
# update.sh
# AI Teacher Bot - Universal Update Script

set -e

echo "========================================"
echo "🔄 AI Teacher Bot - Update"
echo "========================================"

# Dynamic Directory Path
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# 1. Pull latest code (if git repository)
if [ -d ".git" ]; then
    echo "📥 Pulling latest code from Git..."
    git pull || echo "⚠️ Git pull failed, continuing with local files..."
fi

# 2. Activate virtual environment
if [ -d "venv" ]; then
    echo "🔄 Activating virtual environment..."
    source venv/bin/activate
fi

# 3. Install / Update dependencies
if [ -f "requirements.txt" ]; then
    echo "📦 Updating dependencies..."
    pip install -r requirements.txt --quiet
fi

# 4. Run migrations
if [ -f "scripts/run_migrations.py" ]; then
    echo "🗄️ Running database migrations..."
    python scripts/run_migrations.py || echo "⚠️ Migrations completed with warnings."
fi

# 5. Smart Service Restart Check (VPS vs PaaS/Direct)
if command -v systemctl >/dev/null 2>&1 && [ -d "/etc/systemd/system" ] && [ "$(id -u)" -eq 0 ]; then
    echo "⚙️ Restarting systemd service..."
    systemctl restart ai-teacher-bot
    echo ""
    echo "✅ Update & Restart Complete!"
    echo "📊 Status: systemctl status ai-teacher-bot"
    echo "📜 Logs  : journalctl -u ai-teacher-bot -f"
else
    echo "☁️ Non-systemd / Cloud PaaS environment detected."
    echo "✅ Files updated! (Cloud platform will auto-restart if configured)"
fi

echo "========================================"

