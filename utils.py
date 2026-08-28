# utils.py
"""
General utility functions for AI Teacher Bot.

Provides:
- Retry mechanism with exponential backoff
- Text processing (chunking, sanitization, truncation)
- Hash generation
- Validation helpers
- Date/time helpers
"""
import re
import time
import hashlib
import logging
import functools
from typing import Any, Callable, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# ==================== RETRY MECHANISM ====================
def retry(
    max_attempts: int = 3,
    delay: float = 2.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
    on_failure: Optional[Callable] = None,
):
    """
    Decorator for retrying functions on failure.
    
    Implements exponential backoff strategy.
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries (seconds)
        backoff: Multiplier for delay on each retry
        exceptions: Tuple of exceptions to catch
        on_failure: Optional callback function on final failure
    
    Returns:
        Decorated function
    
    Example:
        @retry(max_attempts=3, delay=1.0, backoff=2.0, exceptions=(TimeoutError,))
        def my_function():
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            current_delay = delay
            
            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        if on_failure:
                            on_failure(e)
                        raise
                    
                    logger.warning(
                        f"{func.__name__} attempt {attempt}/{max_attempts} failed: {e}. "
                        f"Retrying in {current_delay:.1f}s"
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            return None
        return wrapper
    return decorator


# ==================== TEXT PROCESSING ====================
def chunk_text(text: str, max_length: int = 4000) -> List[str]:
    """
    Split text into chunks for Telegram message limit (4096 chars).
    
    Preserves line structure where possible.
    Falls back to word splitting for very long lines.
    
    Args:
        text: Input text to chunk
        max_length: Maximum chunk length (default 4000 for Telegram)
    
    Returns:
        List of text chunks
    """
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    current = ""
    
    # Split by lines first
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > max_length:
            # Current chunk is full
            if current:
                chunks.append(current.strip())
                current = line
            else:
                # Single line too long, split by words
                words = line.split(" ")
                for word in words:
                    if len(current) + len(word) + 1 > max_length:
                        if current:
                            chunks.append(current.strip())
                            current = word
                        else:
                            # Word too long, hard split
                            chunks.append(word[:max_length])
                            current = word[max_length:]
                    else:
                        current = f"{current} {word}" if current else word
        else:
            current = f"{current}\n{line}" if current else line
    
    if current:
        chunks.append(current.strip())
    
    return chunks


def sanitize_html(text: str) -> str:
    """
    Escape HTML special characters for Telegram HTML parse mode.
    
    Args:
        text: Input text to sanitize
    
    Returns:
        Sanitized text with HTML entities
    """
    escape_map = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#x27;",
    }
    return "".join(escape_map.get(c, c) for c in text)


def truncate_text(text: str, max_length: int = 100) -> str:
    """
    Truncate text to specified length with ellipsis.
    
    Args:
        text: Input text
        max_length: Maximum length
    
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def strip_markdown(text: str) -> str:
    """
    Remove Markdown formatting from text.
    
    Args:
        text: Input text with Markdown
    
    Returns:
        Plain text
    """
    # Remove headers
    text = re.sub(r"#{1,6}\s*", "", text)
    # Remove bold/italic
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    # Remove inline code
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Remove links
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    return text


# ==================== HASH GENERATION ====================
def generate_hash(text: str, algorithm: str = "sha256") -> str:
    """
    Generate hash of given text.
    
    Args:
        text: Input text
        algorithm: Hash algorithm (sha256, md5, etc.)
    
    Returns:
        Hash string
    """
    hash_func = getattr(hashlib, algorithm)
    return hash_func(text.encode("utf-8")).hexdigest()


def generate_lesson_id(month: str, day_number: int, lesson_type: str) -> str:
    """
    Generate unique lesson ID.
    
    Format: {month}_{day_number}_{lesson_type}
    
    Args:
        month: Month identifier (e.g., "python_month_1")
        day_number: Day number (1-31)
        lesson_type: Lesson type (morning_lesson or evening_practice)
    
    Returns:
        Unique lesson ID string
    """
    return f"{month}_{day_number}_{lesson_type}"


# ==================== VALIDATION ====================
def is_valid_telegram_token(token: str) -> bool:
    """
    Validate Telegram bot token format.
    
    Format: {bot_id}:{random_string}
    
    Args:
        token: Telegram bot token
    
    Returns:
        True if valid, False otherwise
    """
    pattern = r"^\d+:[A-Za-z0-9_-]{35}$"
    return bool(re.match(pattern, token))


def is_valid_channel_id(channel_id: str) -> bool:
    """
    Validate Telegram channel ID format.
    
    Accepts:
    - @username
    - -100{channel_id} (supergroup/channel)
    - Numeric ID
    
    Args:
        channel_id: Channel ID or username
    
    Returns:
        True if valid, False otherwise
    """
    if channel_id.startswith("@"):
        return len(channel_id) > 1
    if channel_id.startswith("-100"):
        return channel_id[4:].isdigit()
    return channel_id.isdigit()


def is_valid_time_format(time_str: str) -> bool:
    """
    Validate time string format (HH:MM).
    
    Args:
        time_str: Time string
    
    Returns:
        True if valid
    """
    pattern = r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$"
    return bool(re.match(pattern, time_str))


# ==================== DATE/TIME HELPERS ====================
def get_current_timestamp() -> str:
    """Get current timestamp in ISO format."""
    return datetime.now().isoformat()


def get_current_date() -> str:
    """Get current date in YYYY-MM-DD format."""
    return datetime.now().strftime("%Y-%m-%d")


def get_current_hour() -> int:
    """Get current hour (0-23)."""
    return datetime.now().hour


def is_morning(hour: int) -> bool:
    """
    Check if given hour is morning.
    
    Args:
        hour: Hour (0-23)
    
    Returns:
        True if morning (5-11)
    """
    return 5 <= hour < 12


def is_evening(hour: int) -> bool:
    """
    Check if given hour is evening.
    
    Args:
        hour: Hour (0-23)
    
    Returns:
        True if evening (17-22)
    """
    return 17 <= hour < 22


def time_until(target_hour: int, target_minute: int) -> float:
    """
    Calculate seconds until target time.
    
    Args:
        target_hour: Target hour (0-23)
        target_minute: Target minute (0-59)
    
    Returns:
        Seconds until target time
    """
    now = datetime.now()
    target = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
    
    if target <= now:
        target += timedelta(days=1)
    
    return (target - now).total_seconds()
