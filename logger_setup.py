# logger_setup.py
"""
Logging configuration for AI Teacher Bot.
Provides centralized logging setup with console and rotating file handlers.

Features:
- Console logging for development
- Rotating file logging for production
- Configurable log level
- No duplicate handlers
- Third-party library noise reduction
- Secret-safe logging (no tokens or API keys)
"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional


def _create_log_directory(log_file: str) -> None:
    """
    Create log directory if it doesn't exist.
    
    Args:
        log_file: Path to log file
    """
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)


def _get_log_level(level_str: str) -> int:
    """
    Convert string log level to logging constant.
    
    Args:
        level_str: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        Logging level constant
    """
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    return level_map.get(level_str.upper(), logging.INFO)


def _create_formatter() -> logging.Formatter:
    """
    Create log formatter with consistent format.
    
    Returns:
        Logging formatter
    """
    return logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def _create_console_handler(
    formatter: logging.Formatter,
    level: int
) -> logging.StreamHandler:
    """
    Create console handler for logging.
    
    Args:
        formatter: Log formatter
        level: Logging level
    
    Returns:
        Console handler
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.setLevel(level)
    return handler


def _create_file_handler(
    formatter: logging.Formatter,
    level: int,
    log_file: str,
    max_bytes: int,
    backup_count: int
) -> RotatingFileHandler:
    """
    Create rotating file handler for logging.
    
    Args:
        formatter: Log formatter
        level: Logging level
        log_file: Log file path
        max_bytes: Maximum file size before rotation
        backup_count: Number of backup files to keep
    
    Returns:
        Rotating file handler
    """
    handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8"
    )
    handler.setFormatter(formatter)
    handler.setLevel(level)
    return handler


def _configure_third_party_loggers() -> None:
    """
    Configure third-party loggers to reduce noise.
    
    Common libraries that produce verbose logging are set to WARNING level.
    """
    noisy_loggers = [
        "urllib3",
        "requests",
        "apscheduler",
        "telethon",
        "pyrogram",
        "httpx",
        "httpcore",
        "asyncio",
    ]
    
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def _remove_existing_handlers(logger: logging.Logger) -> None:
    """
    Remove all existing handlers from logger.
    Prevents duplicate log entries when setup_logging is called multiple times.
    
    Args:
        logger: Logger instance
    """
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)


def setup_logging(
    level: str = "INFO",
    log_file: str = "logs/app.log",
    max_bytes: int = 5242880,
    backup_count: int = 3
) -> logging.Logger:
    """
    Setup and configure logging for the entire application.
    
    This function should be called once at application startup.
    It configures:
    - Root logger level
    - Console handler for stdout
    - Rotating file handler for persistent logs
    - Third-party logger noise reduction
    
    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file
        max_bytes: Maximum log file size before rotation (default 5MB)
        backup_count: Number of backup files to keep (default 3)
    
    Returns:
        Root logger instance
    """
    # Create log directory
    _create_log_directory(log_file)
    
    # Get logging level
    log_level = _get_log_level(level)
    
    # Create formatter
    formatter = _create_formatter()
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers to avoid duplicates
    _remove_existing_handlers(root_logger)
    
    # Add console handler
    console_handler = _create_console_handler(formatter, log_level)
    root_logger.addHandler(console_handler)
    
    # Add file handler
    file_handler = _create_file_handler(
        formatter,
        log_level,
        log_file,
        max_bytes,
        backup_count
    )
    root_logger.addHandler(file_handler)
    
    # Configure third-party loggers
    _configure_third_party_loggers()
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.
    
    Args:
        name: Logger name (usually __name__)
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def log_error(
    logger: logging.Logger,
    error: Exception,
    context: Optional[str] = None
) -> None:
    """
    Log an error with optional context.
    
    Args:
        logger: Logger instance
        error: Exception object
        context: Optional context message
    """
    if context:
        logger.error(f"{context}: {error}", exc_info=True)
    else:
        logger.error(f"Error: {error}", exc_info=True)


def log_warning(
    logger: logging.Logger,
    message: str,
    **kwargs
) -> None:
    """
    Log a warning message with optional data.
    
    Args:
        logger: Logger instance
        message: Warning message
        **kwargs: Additional data to log
    """
    if kwargs:
        data_str = ", ".join(f"{k}={v}" for k, v in kwargs.items())
        logger.warning(f"{message} | {data_str}")
    else:
        logger.warning(message)


def log_info(
    logger: logging.Logger,
    message: str,
    **kwargs
) -> None:
    """
    Log an info message with optional data.
    
    Args:
        logger: Logger instance
        message: Info message
        **kwargs: Additional data to log
    """
    if kwargs:
        data_str = ", ".join(f"{k}={v}" for k, v in kwargs.items())
        logger.info(f"{message} | {data_str}")
    else:
        logger.info(message)


def log_debug(
    logger: logging.Logger,
    message: str,
    **kwargs
) -> None:
    """
    Log a debug message with optional data.
    
    Args:
        logger: Logger instance
        message: Debug message
        **kwargs: Additional data to log
    """
    if kwargs:
        data_str = ", ".join(f"{k}={v}" for k, v in kwargs.items())
        logger.debug(f"{message} | {data_str}")
    else:
        logger.debug(message)
