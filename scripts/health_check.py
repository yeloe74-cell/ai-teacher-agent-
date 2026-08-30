# scripts/health_check.py
"""
AI Teacher Bot - Health Check

Checks if bot is running and responsive.
Sends results to Owner.

Usage:
    python scripts/health_check.py
"""

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def setup_logging():
    """Setup logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )


def check_database():
    """Check database health."""
    try:
        from database import SQLiteDatabase

        db = SQLiteDatabase()
        db.query_one("SELECT 1")
        db.close()
        return True, "Database OK"
    except Exception as exc:
        return False, f"Database error: {exc}"


def check_telegram():
    """Check Telegram bot."""
    try:
        from modules.telegram_client import create_telegram_client

        telegram = create_telegram_client()

        if telegram.verify_bot_token():
            return True, "Telegram OK"
        else:
            return False, "Telegram token invalid"
    except Exception as exc:
        return False, f"Telegram error: {exc}"


def check_scheduler_state():
    """Check scheduler state."""
    try:
        from database import SQLiteDatabase

        db = SQLiteDatabase()
        row = db.query_one(
            "SELECT value FROM app_state WHERE key='paused'"
        )

        paused = str(row.get("value", "0")) == "1" if row else False
        db.close()

        if paused:
            return True, "Scheduler PAUSED"
        else:
            return True, "Scheduler RUNNING"
    except Exception as exc:
        return False, f"Scheduler check error: {exc}"


def send_report_to_owner(report: str):
    """Send health report to Owner."""
    try:
        from config import get_config
        from modules.telegram_client import create_telegram_client

        config = get_config()

        if not config.owner_user_id:
            return

        telegram = create_telegram_client()
        telegram.send_message(
            chat_id=config.owner_user_id,
            text=report,
            parse_mode="HTML",
        )

        print("Report sent to Owner")
    except Exception as exc:
        print(f"Failed to send report: {exc}")


def run_health_check():
    """Run all health checks."""
    print("=" * 50)
    print("AI Teacher Bot — Health Check")
    print("=" * 50)

    checks = [
        ("Database", check_database()),
        ("Telegram", check_telegram()),
        ("Scheduler", check_scheduler_state()),
    ]

    report_lines = ["<b>🏥 Health Check Report</b>"]

    all_healthy = True

    for name, (status, message) in checks:
        if status:
            print(f"  ✅ {name}: {message}")
            report_lines.append(f"✅ {name}: {message}")
        else:
            all_healthy = False
            print(f"  ❌ {name}: {message}")
            report_lines.append(f"❌ {name}: {message}")

    report_lines.append("")
    report_lines.append(
        "✅ All systems healthy" if all_healthy else "⚠️ Some checks failed"
    )

    report = "\n".join(report_lines)

    print("\n" + "=" * 50)
    print("Sending report to Owner...")
    send_report_to_owner(report)

    return all_healthy


if __name__ == "__main__":
    setup_logging()
    success = run_health_check()
    sys.exit(0 if success else 1)
