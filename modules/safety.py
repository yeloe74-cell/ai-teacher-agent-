cat << 'EOF' > modules/safety.py
"""
Safety & Error Handling for AI Teacher Bot.

Part 8 - Safety & Error Handling

Handles:
- Emergency stop
- Rate limiting
- Safe execution wrapper
- Input sanitization
"""

import logging
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional

from config import Config, get_config
from database import DatabaseInterface

logger = logging.getLogger(__name__)


class SafetyError(Exception):
    """Base exception for safety errors."""

    pass


class EmergencyStoppedError(SafetyError):
    """Raised when emergency stop is active."""

    pass


class RateLimitError(SafetyError):
    """Raised when rate limit is exceeded."""

    pass


class SafetyManager:
    """
    Manages safety controls for the bot.

    Features:
    - Emergency stop check
    - Rate limiting
    - Safe execution
    - Input sanitization
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        database: Optional[DatabaseInterface] = None,
    ):
        self.config = config or get_config()
        self.database = database
        self._last_request_time: Dict[str, float] = {}
        self._request_count: Dict[str, int] = {}

        logger.debug("SafetyManager initialized")

    # ========================================================
    # EMERGENCY STOP
    # ========================================================

    def is_emergency_stopped(self) -> bool:
        """Check if emergency stop is active."""
        if not self.database:
            return False

        try:
            row = self.database.query_one(
                "SELECT value FROM app_state WHERE key='emergency_stop'"
            )
            return str(row.get("value", "0")) == "1" if row else False
        except Exception:
            return False

    def set_emergency_stop(self, active: bool) -> bool:
        """Set emergency stop state."""
        if not self.database:
            return False

        try:
            self.database.execute(
                """
                INSERT OR REPLACE INTO app_state (key, value, updated_at)
                VALUES ('emergency_stop', ?, CURRENT_TIMESTAMP)
                """,
                ("1" if active else "0",),
            )
            logger.warning(
                f"Emergency stop: {'ACTIVE' if active else 'INACTIVE'}"
            )
            return True
        except Exception as exc:
            logger.error(f"Failed to set emergency stop: {exc}")
            return False

    def check_safe_to_run(self) -> bool:
        """Check if bot is safe to run operations."""
        if self.is_emergency_stopped():
            logger.warning("Emergency stop active — operation blocked")
            return False
        return True

    # ========================================================
    # RATE LIMITING
    # ========================================================

    def check_rate_limit(
        self,
        key: str,
        max_requests: int = 30,
        window_seconds: int = 60,
    ) -> bool:
        """
        Check if operation is within rate limit.

        Args:
            key: Unique key for this operation type
            max_requests: Maximum requests in window
            window_seconds: Time window in seconds

        Returns:
            True if allowed, False if rate limited
        """
        now = time.time()
        last_time = self._last_request_time.get(key, 0)

        # Reset count if window has passed
        if now - last_time >= window_seconds:
            self._request_count[key] = 0
            self._last_request_time[key] = now

        count = self._request_count.get(key, 0)
        if count >= max_requests:
            logger.warning(f"Rate limit exceeded for {key}")
            return False

        self._request_count[key] = count + 1
        return True

    def wait_if_rate_limited(
        self,
        key: str,
        max_requests: int = 30,
        window_seconds: int = 60,
    ) -> None:
        """Wait until rate limit allows operation."""
        while not self.check_rate_limit(key, max_requests, window_seconds):
            wait_time = min(window_seconds, 5)
            logger.info(f"Rate limited for {key}, waiting {wait_time}s")
            time.sleep(wait_time)

    # ========================================================
    # SAFE EXECUTION
    # ========================================================

    def safe_execute(
        self,
        func: Callable,
        *args,
        **kwargs,
    ) -> Optional[Any]:
        """
        Safely execute a function with error handling.
        Never raises — returns None on failure.
        """
        try:
            if not self.check_safe_to_run():
                return None

            return func(*args, **kwargs)

        except Exception as exc:
            logger.exception(f"Safe execution failed: {func.__name__}: {exc}")
            return None

    # ========================================================
    # INPUT SANITIZATION
    # ========================================================

    @staticmethod
    def sanitize_text(text: str, max_length: int = 4000) -> str:
        """Sanitize user input text."""
        if not text:
            return ""

        # Strip whitespace
        text = text.strip()

        # Truncate
        if len(text) > max_length:
            text = text[:max_length]

        return text

    @staticmethod
    def sanitize_group_id(group_id: Any) -> str:
        """Sanitize group ID."""
        return str(group_id or "").strip().replace("@", "")

    @staticmethod
    def sanitize_user_id(user_id: Any) -> str:
        """Sanitize user ID."""
        return str(user_id or "").strip()

    # ========================================================
    # DECORATOR
    # ========================================================

    def safe_operation(self, func: Callable) -> Callable:
        """
        Decorator for safe operation execution.
        Automatically checks emergency stop and handles errors.
        """

        @wraps(func)
        def wrapper(*args, **kwargs):
            if not self.check_safe_to_run():
                return None

            try:
                return func(*args, **kwargs)
            except Exception as exc:
                logger.exception(f"Operation failed: {func.__name__}: {exc}")
                return None

        return wrapper


# ============================================================
# FACTORY
# ============================================================


def create_safety_manager(
    config: Optional[Config] = None,
    database: Optional[DatabaseInterface] = None,
) -> SafetyManager:
    """Factory function for SafetyManager."""
    return SafetyManager(
        config=config,
        database=database,
    )
EOF
  
