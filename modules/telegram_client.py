# modules/telegram_client.py
"""
Telegram Bot API client using raw HTTP requests.

Provides:
- Message sending with auto-chunking
- Message forwarding
- Rate limit handling
- Error handling with retry support
"""
import logging
import time
import requests
from typing import Any, Dict, Optional

from config import Config, get_config
from utils import retry, chunk_text

logger = logging.getLogger(__name__)


class TelegramError(Exception):
    """Custom exception for Telegram API errors."""
    pass


class TelegramRateLimitError(TelegramError):
    """Raised when Telegram API rate limit is hit."""
    pass


class TelegramTimeoutError(TelegramError):
    """Raised when Telegram API request times out."""
    pass


class TelegramClient:
    """
    Telegram Bot API client.
    
    Handles all Telegram operations via HTTP requests.
    Token is never logged in full - only masked version.
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize Telegram client.
        
        Args:
            config: Config instance (uses get_config() if None)
        """
        self.config = config or get_config()
        self.bot_token = self.config.telegram_bot_token
        self.timeout = self.config.telegram_timeout
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        
        # Log masked token for debugging (safe)
        masked_token = self._mask_token(self.bot_token)
        logger.debug(f"Telegram client initialized with token: {masked_token}")
    
    @staticmethod
    def _mask_token(token: str) -> str:
        """
        Return masked version of token for safe logging.
        
        Args:
            token: Bot token
        
        Returns:
            Masked token (e.g., "1234...abcd")
        """
        if not token or len(token) < 10:
            return "***"
        return f"{token[:4]}...{token[-4:]}"
    
    def _build_url(self, endpoint: str) -> str:
        """Build full Telegram API URL."""
        return f"{self.base_url}/{endpoint}"
    
    def _handle_rate_limit(self, response: requests.Response) -> None:
        """
        Handle HTTP 429 rate limit.
        
        Extracts retry_after from headers or uses default wait time.
        
        Args:
            response: HTTP response
        
        Raises:
            TelegramRateLimitError: Always raised after logging
        """
        retry_after = response.headers.get("retry-after")
        
        if retry_after:
            try:
                wait_time = int(retry_after)
            except ValueError:
                wait_time = 30
        else:
            wait_time = 30
        
        logger.warning(f"Rate limited. Waiting {wait_time}s before retry")
        time.sleep(wait_time)
        raise TelegramRateLimitError(f"Rate limited. Retry after {wait_time}s")
    
    @retry(
        max_attempts=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(requests.RequestException, TelegramRateLimitError),
    )
    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make request to Telegram Bot API.
        
        Args:
            method: HTTP method (GET or POST)
            endpoint: API endpoint
            data: Request payload
        
        Returns:
            API response JSON
        
        Raises:
            TelegramTimeoutError: If request times out
            TelegramRateLimitError: If rate limited
            TelegramError: For other API errors
        """
        url = self._build_url(endpoint)
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, params=data, timeout=self.timeout)
            else:
                response = requests.post(url, json=data, timeout=self.timeout)
            
            # Handle rate limiting
            if response.status_code == 429:
                self._handle_rate_limit(response)
            
            response.raise_for_status()
            result = response.json()
            
            if not result.get("ok", False):
                error_msg = result.get("description", "Unknown error")
                logger.error(f"Telegram API error: {error_msg}")
                raise TelegramError(f"Telegram API error: {error_msg}")
            
            return result
            
        except requests.Timeout:
            logger.error(f"Telegram API timeout after {self.timeout}s")
            raise TelegramTimeoutError(f"Timeout after {self.timeout}s")
        except requests.RequestException as e:
            logger.error(f"Telegram request failed: {e}")
            raise TelegramError(f"Request failed: {e}")
    
    def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str = "HTML",
        disable_preview: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        Send text message to a chat.
        
        Automatically splits long messages into chunks.
        Adds delay between chunks to avoid rate limits.
        
        Args:
            chat_id: Chat ID or channel username
            text: Message text
            parse_mode: "HTML" or "Markdown"
            disable_preview: Disable web page preview
        
        Returns:
            API response for last chunk, or None if no chunks
        """
        chunks = chunk_text(text)
        results = []
        
        logger.debug(f"Sending message to {chat_id} ({len(chunks)} chunks)")
        
        for i, chunk in enumerate(chunks):
            payload = {
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": parse_mode,
                "disable_web_page_preview": disable_preview,
            }
            
            try:
                result = self._make_request("POST", "sendMessage", payload)
                results.append(result)
            except TelegramError as e:
                logger.error(f"Failed to send chunk {i+1}/{len(chunks)}: {e}")
                # Continue with next chunk even if one fails
                continue
            
            # Rate limit protection between chunks
            if len(chunks) > 1 and i < len(chunks) - 1:
                time.sleep(1)
        
        return results[-1] if results else None
    
    def forward_message(
        self,
        from_chat_id: str,
        message_id: int,
        to_chat_id: str,
    ) -> Dict[str, Any]:
        """
        Forward a message from one chat to another.
        
        Args:
            from_chat_id: Source chat ID
            message_id: Message ID to forward
            to_chat_id: Destination chat ID
        
        Returns:
            API response
        """
        payload = {
            "chat_id": to_chat_id,
            "from_chat_id": from_chat_id,
            "message_id": message_id,
        }
        
        logger.debug(
            f"Forwarding message {message_id} from {from_chat_id} to {to_chat_id}"
        )
        return self._make_request("POST", "forwardMessage", payload)
    
    def get_me(self) -> Dict[str, Any]:
        """Get bot information."""
        return self._make_request("GET", "getMe")
    
    def get_chat(self, chat_id: str) -> Dict[str, Any]:
        """
        Get chat information.
        
        Args:
            chat_id: Chat ID
        
        Returns:
            Chat information
        """
        return self._make_request("GET", "getChat", {"chat_id": chat_id})
    
    def verify_bot_token(self) -> bool:
        """
        Verify if bot token is valid.
        
        Returns:
            True if token is valid
        """
        try:
            result = self.get_me()
            if result and result.get("ok"):
                bot_info = result.get("result", {})
                logger.info(f"Bot verified: @{bot_info.get('username', 'unknown')}")
                return True
            return False
        except TelegramError:
            return False


def create_telegram_client(config: Optional[Config] = None) -> TelegramClient:
    """
    Factory function for TelegramClient.
    
    Args:
        config: Optional Config instance
    
    Returns:
        TelegramClient instance
    """
    return TelegramClient(config)
