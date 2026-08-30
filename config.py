# config.py
"""
Central configuration for AI Teacher Bot.
Loads environment variables from .env file.
Validates required configuration values.
Uses dataclasses for type safety and maintainability.

This module provides:
- Config dataclass for all application settings
- get_config() factory function for dependency injection
- Validation methods for required fields
- Helper methods for accessing configuration groups
"""

import os
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Config:
    """
    Application configuration class.

    All values are loaded from environment variables.
    Sensitive values (tokens, API keys) are never logged.

    Attributes:
        cf_account_id: Cloudflare account ID
        cf_api_token: Cloudflare API token
        cf_ai_model: Workers AI model name
        cf_d1_database_id: Cloudflare D1 database ID
        telegram_bot_token: Telegram bot token
        telegram_channel_id: Telegram channel ID/username
        owner_user_id: Owner's Telegram user ID
        morning_post_time: Morning lesson post time (HH:MM)
        evening_post_time: Evening practice post time (HH:MM)
        timezone: Application timezone
        log_level: Logging level
        log_file: Log file path
        log_max_bytes: Max log file size before rotation
        log_backup_count: Number of backup log files
        db_backend: Database backend ('sqlite' or 'd1')
        sqlite_db_path: SQLite database path
        db_timeout: Database timeout in seconds
        ai_timeout: AI API timeout in seconds
        telegram_timeout: Telegram API timeout in seconds
        max_retry_attempts: Maximum retry attempts
        retry_delay: Initial retry delay in seconds
        retry_backoff: Retry delay multiplier
        max_tokens_morning: Max tokens for morning lessons
        max_tokens_evening: Max tokens for evening practices
        temperature: AI temperature setting
        auto_share_default: Default auto-share setting for groups
        max_daily_shares_per_group: Max daily shares per group
        emergency_stop: Emergency stop flag
        maintenance_mode: Maintenance mode flag
    """

    # ==================== Cloudflare Workers AI ====================
    cf_account_id: str = field(default_factory=lambda: os.getenv("CF_ACCOUNT_ID", ""))
    cf_api_token: str = field(default_factory=lambda: os.getenv("CF_API_TOKEN", ""))
    cf_ai_model: str = field(
        default_factory=lambda: os.getenv("CF_AI_MODEL", "@cf/meta/llama-3-8b-instruct")
    )

    # ==================== Cloudflare D1 Database ====================
    cf_d1_database_id: str = field(
        default_factory=lambda: os.getenv("CF_D1_DATABASE_ID", "")
    )
    cf_d1_api_url: str = field(default_factory=lambda: os.getenv("CF_D1_API_URL", ""))

    # ==================== Telegram Bot ====================
    telegram_bot_token: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", "")
    )
    telegram_channel_id: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_CHANNEL_ID", "")
    )

    # ==================== Owner ====================
    owner_user_id: str = field(default_factory=lambda: os.getenv("OWNER_USER_ID", ""))

    # ==================== Schedule ====================
    morning_post_time: str = field(
        default_factory=lambda: os.getenv("MORNING_POST_TIME", "08:00")
    )
    evening_post_time: str = field(
        default_factory=lambda: os.getenv("EVENING_POST_TIME", "20:00")
    )
    timezone: str = field(default_factory=lambda: os.getenv("TIMEZONE", "Asia/Yangon"))

    # ==================== Logging ====================
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    log_file: str = field(default_factory=lambda: os.getenv("LOG_FILE", "logs/app.log"))
    log_max_bytes: int = field(
        default_factory=lambda: int(os.getenv("LOG_MAX_BYTES", "5242880"))
    )
    log_backup_count: int = field(
        default_factory=lambda: int(os.getenv("LOG_BACKUP_COUNT", "3"))
    )

    # ==================== Database ====================
    db_backend: str = field(default_factory=lambda: os.getenv("DB_BACKEND", "sqlite"))
    sqlite_db_path: str = field(
        default_factory=lambda: os.getenv("SQLITE_DB_PATH", "data/app.db")
    )
    db_timeout: int = field(default_factory=lambda: int(os.getenv("DB_TIMEOUT", "30")))

    # ==================== API Timeouts ====================
    ai_timeout: int = field(default_factory=lambda: int(os.getenv("AI_TIMEOUT", "60")))
    telegram_timeout: int = field(
        default_factory=lambda: int(os.getenv("TELEGRAM_TIMEOUT", "30"))
    )

    # ==================== Retry Configuration ====================
    max_retry_attempts: int = field(
        default_factory=lambda: int(os.getenv("MAX_RETRY_ATTEMPTS", "3"))
    )
    retry_delay: float = field(
        default_factory=lambda: float(os.getenv("RETRY_DELAY", "2.0"))
    )
    retry_backoff: float = field(
        default_factory=lambda: float(os.getenv("RETRY_BACKOFF", "2.0"))
    )

    # ==================== Content Generation ====================
    max_tokens_morning: int = field(
        default_factory=lambda: int(os.getenv("MAX_TOKENS_MORNING", "1000"))
    )
    max_tokens_evening: int = field(
        default_factory=lambda: int(os.getenv("MAX_TOKENS_EVENING", "800"))
    )
    temperature: float = field(
        default_factory=lambda: float(os.getenv("TEMPERATURE", "0.7"))
    )

    # ==================== Safety ====================
    auto_share_default: bool = field(
        default_factory=lambda: os.getenv("AUTO_SHARE_DEFAULT", "0") == "1"
    )
    max_daily_shares_per_group: int = field(
        default_factory=lambda: int(os.getenv("MAX_DAILY_SHARES_PER_GROUP", "2"))
    )
    emergency_stop: bool = field(
        default_factory=lambda: os.getenv("EMERGENCY_STOP", "0") == "1"
    )
    maintenance_mode: bool = field(
        default_factory=lambda: os.getenv("MAINTENANCE_MODE", "0") == "1"
    )

    # ==================== Validation ====================
    def validate(self) -> bool:
        """
        Validate required configuration values.

        Returns:
            True if all required values are present, False otherwise
        """
        required_fields = {
            "cf_account_id": self.cf_account_id,
            "cf_api_token": self.cf_api_token,
            "telegram_bot_token": self.telegram_bot_token,
            "telegram_channel_id": self.telegram_channel_id,
        }

        missing_fields = [name for name, value in required_fields.items() if not value]

        if missing_fields:
            logger.error(f"Missing required configuration: {', '.join(missing_fields)}")
            logger.error("Please check your .env file and add these values.")
            return False

        # Validate D1 configuration if selected
        if self.db_backend == "d1" and not self.cf_d1_database_id:
            logger.error("D1 backend selected but CF_D1_DATABASE_ID is missing")
            return False

        return True

    # ==================== Getter Methods ====================
    def get_ai_config(self) -> Dict[str, Any]:
        """Get AI-related configuration as dictionary."""
        return {
            "account_id": self.cf_account_id,
            "api_token": self.cf_api_token,
            "model": self.cf_ai_model,
            "timeout": self.ai_timeout,
            "max_tokens_morning": self.max_tokens_morning,
            "max_tokens_evening": self.max_tokens_evening,
            "temperature": self.temperature,
        }

    def get_telegram_config(self) -> Dict[str, Any]:
        """Get Telegram-related configuration as dictionary."""
        return {
            "bot_token": self.telegram_bot_token,
            "channel_id": self.telegram_channel_id,
            "timeout": self.telegram_timeout,
        }

    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration as dictionary."""
        return {
            "backend": self.db_backend,
            "sqlite_path": self.sqlite_db_path,
            "d1_database_id": self.cf_d1_database_id,
            "timeout": self.db_timeout,
        }

    def get_retry_config(self) -> Dict[str, Any]:
        """Get retry configuration as dictionary."""
        return {
            "max_attempts": self.max_retry_attempts,
            "delay": self.retry_delay,
            "backoff": self.retry_backoff,
        }

    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration as dictionary."""
        return {
            "level": self.log_level,
            "file": self.log_file,
            "max_bytes": self.log_max_bytes,
            "backup_count": self.log_backup_count,
        }

    def get_schedule_config(self) -> Dict[str, Any]:
        """Get schedule configuration as dictionary."""
        return {
            "morning_post_time": self.morning_post_time,
            "evening_post_time": self.evening_post_time,
            "timezone": self.timezone,
        }

    def get_safety_config(self) -> Dict[str, Any]:
        """Get safety configuration as dictionary."""
        return {
            "auto_share_default": self.auto_share_default,
            "max_daily_shares_per_group": self.max_daily_shares_per_group,
            "emergency_stop": self.emergency_stop,
            "maintenance_mode": self.maintenance_mode,
        }

    # ==================== State Checks ====================
    def is_emergency_stopped(self) -> bool:
        """Check if emergency stop is active."""
        return self.emergency_stop

    def is_maintenance_mode(self) -> bool:
        """Check if maintenance mode is active."""
        return self.maintenance_mode


# Module-level config cache
_config: Optional[Config] = None


def get_config() -> Config:
    """
    Get or create Config instance.

    Uses module-level caching to avoid creating multiple instances.
    This is the recommended way to access configuration.

    Returns:
        Config instance
    """
    global _config
    if _config is None:
        _config = Config()
    return _config


def reset_config() -> None:
    """
    Reset cached config instance.
    Useful for testing when environment variables change.
    """
    global _config
    _config = None
