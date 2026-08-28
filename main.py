# main.py
"""
AI Teacher Bot - Main Entry Point.

Starts the scheduler for automated lesson publishing.
"""
import logging
import sys

from config import get_config
from logger_setup import setup_logging
from modules.scheduler import create_scheduler


def main() -> None:
    """
    Main entry point.
    """
    # Load config
    config = get_config()
    
    # Setup logging
    log_config = config.get_logging_config()
    setup_logging(
        level=log_config["level"],
        log_file=log_config["file"],
        max_bytes=log_config["max_bytes"],
        backup_count=log_config["backup_count"],
    )
    
    logger = logging.getLogger(__name__)
    
    # Validate config
    if not config.validate():
        logger.error("Invalid configuration. Exiting.")
        sys.exit(1)
    
    logger.info("=" * 60)
    logger.info("AI Teacher Bot - Starting")
    logger.info(f"Timezone: {config.timezone}")
    logger.info(f"Morning post: {config.morning_post_time}")
    logger.info(f"Evening post: {config.evening_post_time}")
    logger.info("=" * 60)
    
    # Create and start scheduler
    try:
        scheduler = create_scheduler(config)
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
