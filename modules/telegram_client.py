# modules/telegram_client.py
"""
Telegram Bot API client

Part 1 features:
- Send messages
- Automatic long-message chunking
- Forward messages
- Get bot information
- Get chat information
- Bot token verification
- Basic retry support
- Rate-limit handling
- Response validation
- Safe token logging
"""

import logging
import time
from typing import Any, Dict, List, Optional

import requests

from config import Config, get_config
from utils import retry, chunk_text

logger = logging.getLogger(__name__)


# ================================================================
# EXCEPTIONS
# ================================================================

class TelegramError(Exception):
    """Base exception for Telegram errors."""
    pass


class TelegramTimeoutError(TelegramError):
    """Raised when Telegram API request times out."""
    pass


class TelegramRateLimitError(TelegramError):
    """Raised when Telegram API rate limit is reached."""

    def __init__(
        self,
        message: str,
        retry_after: int = 30,
    ):
        super().__init__(message)
        self.retry_after = retry_after


class TelegramResponseError(TelegramError):
    """Raised when Telegram response is invalid."""
    pass


class TelegramConnectionError(TelegramError):
    """Raised when connection to Telegram fails."""
    pass


# ================================================================
# TELEGRAM CLIENT
# ================================================================

class TelegramClient:
    """
    Basic Telegram Bot API client for Part 1 Alpha.

    Handles:
    - sendMessage
    - forwardMessage
    - getMe
    - getChat
    - bot token verification
    - message chunking
    - basic retry
    - rate limits
    """

    # Telegram Bot API message limit
    MAX_MESSAGE_LENGTH = 4096

    # Leave some space so formatting/chunking is safer
    CHUNK_MAX_LENGTH = 3900

    # Delay between message chunks
    CHUNK_DELAY = 0.5

    # Default retry settings
    MAX_ATTEMPTS = 3
    RETRY_DELAY = 1.0
    RETRY_BACKOFF = 2.0

    def __init__(
        self,
        config: Optional[Config] = None,
    ):
        """
        Initialize Telegram client.

        Args:
            config: Config instance.
            Uses get_config() if not provided.
        """
        self.config = config or get_config()

        self.bot_token = self.config.telegram_bot_token
        self.timeout = self.config.telegram_timeout

        if not self.bot_token:
            raise TelegramError(
                "Telegram bot token is missing"
            )

        self.base_url = (
            f"https://api.telegram.org/bot{self.bot_token}"
        )

        logger.debug(
            "Telegram client initialized: %s",
            self._mask_token(self.bot_token),
        )

    # ============================================================
    # TOKEN
    # ============================================================

    @staticmethod
    def _mask_token(token: str) -> str:
        """
        Mask Telegram bot token for logs.

        Example:
            123456789:ABCDEF...
            -> 1234...WXYZ
        """
        if not token or len(token) < 10:
            return "***"

        return f"{token[:4]}...{token[-4:]}"

    # ============================================================
    # URL
    # ============================================================

    def _build_url(
        self,
        endpoint: str,
    ) -> str:
        """Build Telegram API endpoint URL."""
        return f"{self.base_url}/{endpoint}"

    # ============================================================
    # RATE LIMIT
    # ============================================================

    @staticmethod
    def _get_retry_after(
        response: requests.Response,
        data: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Extract Telegram retry_after value.

        Checks:
        1. JSON parameters.retry_after
        2. Retry-After HTTP header
        3. Defaults to 30 seconds
        """

        # Telegram JSON response
        if isinstance(data, dict):

            parameters = data.get("parameters")

            if isinstance(parameters, dict):

                retry_after = parameters.get(
                    "retry_after"
                )

                if retry_after is not None:
                    try:
                        return max(
                            1,
                            int(retry_after),
                        )
                    except (
                        TypeError,
                        ValueError,
                    ):
                        pass

        # HTTP header
        header_value = response.headers.get(
            "Retry-After"
        )

        if header_value:
            try:
                return max(
                    1,
                    int(header_value),
                )
            except (
                TypeError,
                ValueError,
            ):
                pass

        return 30

    # ============================================================
    # RESPONSE VALIDATION
    # ============================================================

    @staticmethod
    def _validate_response(
        data: Any,
    ) -> Dict[str, Any]:
        """
        Validate Telegram API response.
        """

        if not isinstance(data, dict):
            raise TelegramResponseError(
                "Telegram response is not a JSON object"
            )

        if not data.get("ok", False):

            error_code = data.get(
                "error_code",
                "unknown",
            )

            description = data.get(
                "description",
                "Unknown Telegram error",
            )

            raise TelegramError(
                f"Telegram API error "
                f"({error_code}): {description}"
            )

        if "result" not in data:
            raise TelegramResponseError(
                "Telegram response missing result"
            )

        return data

    # ============================================================
    # HTTP REQUEST
    # ============================================================

    @retry(
        max_attempts=MAX_ATTEMPTS,
        delay=RETRY_DELAY,
        backoff=RETRY_BACKOFF,
        exceptions=(
            TelegramTimeoutError,
            TelegramConnectionError,
            TelegramRateLimitError,
            requests.RequestException,
        ),
    )
    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make HTTP request to Telegram API.
        """

        url = self._build_url(endpoint)

        try:

            method = method.upper()

            if method == "GET":

                response = requests.get(
                    url,
                    params=data,
                    timeout=self.timeout,
                )

            elif method == "POST":

                response = requests.post(
                    url,
                    json=data,
                    timeout=self.timeout,
                )

            else:
                raise TelegramError(
                    f"Unsupported HTTP method: {method}"
                )

        except requests.Timeout as e:

            logger.warning(
                "Telegram request timeout after %ss",
                self.timeout,
            )

            raise TelegramTimeoutError(
                f"Telegram timeout after "
                f"{self.timeout}s"
            ) from e

        except requests.ConnectionError as e:

            logger.warning(
                "Telegram connection error: %s",
                e,
            )

            raise TelegramConnectionError(
                f"Telegram connection failed: {e}"
            ) from e

        except requests.RequestException as e:

            logger.warning(
                "Telegram request error: %s",
                e,
            )

            raise

        # --------------------------------------------------------
        # Parse JSON
        # --------------------------------------------------------

        try:
            result = response.json()

        except ValueError as e:

            raise TelegramResponseError(
                "Telegram returned invalid JSON"
            ) from e

        # --------------------------------------------------------
        # Rate limit
        # --------------------------------------------------------

        if response.status_code == 429:

            retry_after = self._get_retry_after(
                response,
                result,
            )

            logger.warning(
                "Telegram rate limit. "
                "Waiting %ss",
                retry_after,
            )

            # Wait according to Telegram
            time.sleep(retry_after)

            raise TelegramRateLimitError(
                f"Rate limited. "
                f"Retry after {retry_after}s",
                retry_after=retry_after,
            )

        # --------------------------------------------------------
        # Server errors
        # --------------------------------------------------------

        if response.status_code >= 500:

            logger.warning(
                "Telegram server error: HTTP %s",
                response.status_code,
            )

            raise TelegramError(
                f"Telegram server error: "
                f"HTTP {response.status_code}"
            )

        # --------------------------------------------------------
        # Client errors
        # --------------------------------------------------------

        if response.status_code >= 400:

            description = "Unknown Telegram error"

            if isinstance(result, dict):
                description = result.get(
                    "description",
                    description,
                )

            raise TelegramError(
                f"Telegram HTTP error "
                f"{response.status_code}: "
                f"{description}"
            )

        # --------------------------------------------------------
        # Validate
        # --------------------------------------------------------

        return self._validate_response(result)

    # ============================================================
    # SEND MESSAGE
    # ============================================================

    def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str = "HTML",
        disable_preview: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        Send message to Telegram.

        Long messages are automatically split.

        Args:
            chat_id:
                Telegram chat ID or @username.

            text:
                Message content.

            parse_mode:
                HTML, Markdown, MarkdownV2 or None.

            disable_preview:
                Disable web page preview.

        Returns:
            Telegram response of the last chunk.
        """

        if not chat_id:
            raise TelegramError(
                "chat_id is required"
            )

        if not text or not text.strip():

            logger.warning(
                "Cannot send empty Telegram message"
            )

            return None

        chunks = chunk_text(
            text,
            max_length=self.CHUNK_MAX_LENGTH,
        )

        logger.debug(
            "Sending Telegram message to %s "
            "(%s chunk(s))",
            chat_id,
            len(chunks),
        )

        results: List[Dict[str, Any]] = []

        for index, chunk in enumerate(
            chunks,
            start=1,
        ):

            payload: Dict[str, Any] = {
                "chat_id": chat_id,
                "text": chunk,
                "disable_web_page_preview":
                    disable_preview,
            }

            if parse_mode:
                payload["parse_mode"] = parse_mode

            try:

                result = self._make_request(
                    "POST",
                    "sendMessage",
                    payload,
                )

                # Verify message object
                telegram_result = result.get(
                    "result"
                )

                if not isinstance(
                    telegram_result,
                    dict,
                ):
                    raise TelegramResponseError(
                        "sendMessage result is invalid"
                    )

                message_id = telegram_result.get(
                    "message_id"
                )

                if message_id is None:
                    raise TelegramResponseError(
                        "sendMessage response "
                        "missing message_id"
                    )

                results.append(result)

                logger.info(
                    "Telegram message sent "
                    "(chunk %s/%s, message_id=%s)",
                    index,
                    len(chunks),
                    message_id,
                )

            except TelegramError:
                logger.exception(
                    "Failed to send Telegram "
                    "message chunk %s/%s",
                    index,
                    len(chunks),
                )
                raise

            if (
                len(chunks) > 1
                and index < len(chunks)
            ):
                time.sleep(
                    self.CHUNK_DELAY
                )

        return results[-1]

    # ============================================================
    # FORWARD MESSAGE
    # ============================================================

    def forward_message(
        self,
        from_chat_id: str,
        message_id: int,
        to_chat_id: str,
    ) -> Dict[str, Any]:
        """
        Forward Telegram message.
        """

        if not from_chat_id:
            raise TelegramError(
                "from_chat_id is required"
            )

        if not to_chat_id:
            raise TelegramError(
                "to_chat_id is required"
            )

        if (
            not isinstance(message_id, int)
            or message_id <= 0
        ):
            raise TelegramError(
                f"Invalid message_id: {message_id}"
            )

        payload = {
            "chat_id": to_chat_id,
            "from_chat_id": from_chat_id,
            "message_id": message_id,
        }

        logger.debug(
            "Forwarding message %s "
            "from %s to %s",
            message_id,
            from_chat_id,
            to_chat_id,
        )

        return self._make_request(
            "POST",
            "forwardMessage",
            payload,
        )

    # ============================================================
    # GET ME
    # ============================================================

    def get_me(self) -> Dict[str, Any]:
        """
        Get Telegram bot information.
        """

        return self._make_request(
            "GET",
            "getMe",
        )

    # ============================================================
    # GET CHAT
    # ============================================================

    def get_chat(
        self,
        chat_id: str,
    ) -> Dict[str, Any]:
        """
        Get Telegram chat information.
        """

        if not chat_id:
            raise TelegramError(
                "chat_id is required"
            )

        return self._make_request(
            "GET",
            "getChat",
            {
                "chat_id": chat_id,
            },
        )

    # ============================================================
    # VERIFY BOT
    # ============================================================

    def verify_bot_token(self) -> bool:
        """
        Verify Telegram bot token.

        Returns:
            True if valid.
            False otherwise.
        """

        try:

            result = self.get_me()

            bot_info = result.get(
                "result"
            )

            if not isinstance(
                bot_info,
                dict,
            ):
                logger.error(
                    "Invalid bot information"
                )
                return False

            username = bot_info.get(
                "username",
                "unknown",
            )

            logger.info(
                "Telegram bot verified: @%s",
                username,
            )

            return True

        except TelegramError as e:

            logger.error(
                "Telegram bot verification failed: %s",
                e,
            )

            return False

        except Exception:

            logger.exception(
                "Unexpected bot verification error"
            )

            return False


# ================================================================
# FACTORY
# ================================================================

def create_telegram_client(
    config: Optional[Config] = None,
) -> TelegramClient:
    """
    Factory function for TelegramClient.
    """

    return TelegramClient(
        config=config
)
