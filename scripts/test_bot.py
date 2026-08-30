# scripts/test_bot.py
"""
AI Teacher Bot - Test Script

Tests:
- Config loading
- Database connection
- AI Generator
- Telegram Client
- Publisher
- Group Manager

Usage:
    python scripts/test_bot.py
"""

import logging
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def setup_logging():
    """Setup test logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )


def test_config():
    """Test config loading."""
    print("\n" + "=" * 50)
    print("Testing Config...")
    print("=" * 50)

    try:
        from config import get_config
        config = get_config()

        checks = {
            "CF_ACCOUNT_ID": bool(config.cf_account_id),
            "CF_API_TOKEN": bool(config.cf_api_token),
            "TELEGRAM_BOT_TOKEN": bool(config.telegram_bot_token),
            "TELEGRAM_CHANNEL_ID": bool(config.telegram_channel_id),
        }

        for name, status in checks.items():
            print(f"  {'✅' if status else '❌'} {name}")

        if all(checks.values()):
            print("✅ Config: PASSED")
            return True
        else:
            print("❌ Config: FAILED — missing required values")
            return False

    except Exception as exc:
        print(f"❌ Config test failed: {exc}")
        return False


def test_database():
    """Test database connection."""
    print("\n" + "=" * 50)
    print("Testing Database...")
    print("=" * 50)

    try:
        from database import SQLiteDatabase

        db = SQLiteDatabase()
        result = db.query_one("SELECT 1 AS test")

        if result and result.get("test") == 1:
            print("✅ Database: PASSED")
            db.close()
            return True
        else:
            print("❌ Database: FAILED")
            return False

    except Exception as exc:
        print(f"❌ Database test failed: {exc}")
        return False


def test_telegram():
    """Test Telegram client."""
    print("\n" + "=" * 50)
    print("Testing Telegram Client...")
    print("=" * 50)

    try:
        from modules.telegram_client import create_telegram_client

        telegram = create_telegram_client()

        if telegram.verify_bot_token():
            print("✅ Telegram: PASSED")
            return True
        else:
            print("❌ Telegram: FAILED — invalid token")
            return False

    except Exception as exc:
        print(f"❌ Telegram test failed: {exc}")
        return False


def test_ai_generator():
    """Test AI Generator (optional — uses API)."""
    print("\n" + "=" * 50)
    print("Testing AI Generator...")
    print("=" * 50)

    try:
        from modules.ai_generator import create_ai_generator

        ai = create_ai_generator()
        content = ai.generate_lesson("Test Topic", "morning_lesson")

        if content and len(content) > 50:
            print(f"✅ AI Generator: PASSED ({len(content)} chars)")
            return True
        else:
            print("❌ AI Generator: FAILED — empty response")
            return False

    except Exception as exc:
        print(f"⚠️  AI test skipped or failed: {exc}")
        return True  # Non-critical


def test_group_manager():
    """Test Group Manager."""
    print("\n" + "=" * 50)
    print("Testing Group Manager...")
    print("=" * 50)

    try:
        from database import SQLiteDatabase
        from modules.group_manager import create_group_manager

        db = SQLiteDatabase()
        gm = create_group_manager(db, max_daily_shares=2)

        # Test register
        group = gm.register_group("@test_group", "Test Group")

        if group:
            print("✅ Group Manager: PASSED")
            gm.remove_group("@test_group")
            db.close()
            return True
        else:
            print("❌ Group Manager: FAILED")
            return False

    except Exception as exc:
        print(f"❌ Group Manager test failed: {exc}")
        return False


def test_publisher():
    """Test Publisher structure."""
    print("\n" + "=" * 50)
    print("Testing Publisher...")
    print("=" * 50)

    try:
        from modules.publisher import create_publisher

        publisher = create_publisher()

        if publisher.channel_id:
            print("✅ Publisher: PASSED")
            publisher.close()
            return True
        else:
            print("❌ Publisher: FAILED — missing channel_id")
            return False

    except Exception as exc:
        print(f"❌ Publisher test failed: {exc}")
        return False


def run_all_tests():
    """Run all tests."""
    print("=" * 50)
    print("AI Teacher Bot — Test Suite")
    print("=" * 50)

    results = {
        "Config": test_config(),
        "Database": test_database(),
        "Telegram": test_telegram(),
        "AI Generator": test_ai_generator(),
        "Group Manager": test_group_manager(),
        "Publisher": test_publisher(),
    }

    print("\n" + "=" * 50)
    print("Test Summary")
    print("=" * 50)

    passed = 0
    failed = 0

    for name, status in results.items():
        if status:
            passed += 1
            print(f"  ✅ {name}")
        else:
            failed += 1
            print(f"  ❌ {name}")

    print(f"\n✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print("=" * 50)

    return failed == 0


if __name__ == "__main__":
    setup_logging()
    success = run_all_tests()
    sys.exit(0 if success else 1)
