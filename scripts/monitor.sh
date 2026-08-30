#!/bin/bash
# monitor.sh
# AI Teacher Bot - Monitoring Script

echo "========================================"
echo "AI Teacher Bot - Monitoring"
echo "========================================"

# Check if bot is running
if systemctl is-active --quiet ai-teacher-bot 2>/dev/null; then
    echo "✅ Bot Status: RUNNING"
else
    echo "❌ Bot Status: NOT RUNNING"
fi

echo ""

# Check memory usage
echo "📊 Memory Usage:"
ps aux | grep "python main.py" | grep -v grep | awk '{print "  PID: "$2" | Memory: "$4"% | CPU: "$3"%"}'

echo ""

# Check recent logs
echo "📜 Recent Logs (last 20 lines):"
if systemctl is-active --quiet ai-teacher-bot 2>/dev/null; then
    journalctl -u ai-teacher-bot -n 20 --no-pager
else
    tail -n 20 logs/app.log 2>/dev/null || echo "No logs found"
fi

echo ""

# Check disk space
echo "💾 Disk Space:"
df -h "$(pwd)" | tail -1 | awk '{print "  Available: "$4" | Used: "$5}'

echo ""

# Health check
echo "🏥 Running Health Check..."
python scripts/health_check.py 2>/dev/null || echo "❌ Health check failed"

echo ""
echo "========================================"
