# modules/admin.py
"""
Admin Command Handler for AI Teacher Bot.

This module is the main entry point for command processing.
It delegates Owner commands to OwnerHandler.

Flow:
    Telegram Update → AdminHandler.handle_message()
                    → OwnerHandler.handle_message()
                    → Command dispatch

Non-owner messages are silently ignored.
"""

import logging
from typing import Any, Dict, Optional

from config import Config, get_config
from database import DatabaseInterface
from modules.group_manager import GroupManager
from modules.owner import OwnerHandler, create_owner_handler
from modules.telegram_client import TelegramClient

logger = logging.getLogger(__name__)


class AdminHandler:
    """
    Main admin command handler.
    
    Delegates all command processing to OwnerHandler.
    Keeps non-owner messages completely ignored.
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        database: Optional[DatabaseInterface] = None,
        telegram: Optional[TelegramClient] = None,
        group_manager: Optional[GroupManager] = None,
    ):
        self.config = config or get_config()
        self.database = database
        self.telegram = telegram
        self.groups = group_manager

        # Create OwnerHandler
        self.owner = create_owner_handler(
            config=self.config,
            database=self.database,
            telegram=self.telegram,
            group_manager=self.groups,
        )

        logger.info("AdminHandler initialized")

    # ========================================================
    # MESSAGE HANDLER
    # ========================================================

    def handle_message(self, update: Dict[str, Any]) -> bool:
        """
        Handle incoming Telegram update.
        
        Steps:
        1. Extract message
        2. Scan for links (any message)
        3. Delegate to OwnerHandler if owner
        4. Ignore non-owner messages
        """
        try:
            message = update.get("message")
            if not message:
                return False

            # Scan any message for links (even from non-owner)
            if self.owner:
                self.owner.scan_message_for_links(message)

            # Owner commands
            if self.owner:
                return self.owner.handle_message(update)

            return False

        except Exception as exc:
            logger.exception(f"Admin handler error: {exc}")
            return False

    # ========================================================
    # DIRECT COMMAND ACCESS (for bot_runner)
    # ========================================================

    def is_owner(self, user_id: Any) -> bool:
        """Check if user is owner."""
        if self.owner:
            return self.owner.is_owner(user_id)
        return False

    def send_to_owner(self, chat_id: Any, text: str) -> None:
        """Send message to Owner via OwnerHandler."""
        if self.owner:
            self.owner._send(chat_id, text)


# ============================================================
# FACTORY
# ============================================================

def create_admin_handler(
    config: Optional[Config] = None,
    database: Optional[DatabaseInterface] = None,
    telegram: Optional[TelegramClient] = None,
    group_manager: Optional[GroupManager] = None,
) -> AdminHandler:
    """Factory function for AdminHandler."""
    return AdminHandler(
        config=config,
        database=database,
        telegram=telegram,
        group_manager=group_manager,
  )
