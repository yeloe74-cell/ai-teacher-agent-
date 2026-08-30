"""
Content publisher for AI Teacher Bot.

Publishing flow:
1. Safety checks
2. Idempotency check
3. AI generation
4. Content validation
5. Telegram publishing
6. Database record

Group sharing flow:
1. Verify group is approved
2. Verify group is enabled
3. Verify auto-share is allowed
4. Forward message to group
"""

import logging
from typing import Any, Dict, Optional

from config import Config, get_config
from database import DatabaseInterface, create_database, DatabaseError
from modules.ai_generator import (
    AIGenerator,
    create_ai_generator,
    AIGeneratorError,
)
from modules.telegram_client import (
    TelegramClient,
    create_telegram_client,
    TelegramError,
)
from utils import (
    generate_lesson_id,
    get_current_timestamp,
)

logger = logging.getLogger(__name__)


class PublisherError(Exception):
    """Custom exception for publishing errors."""

    pass


class Publisher:
    """
    Handles publishing of AI-generated content to Telegram.

    Combines:
    - AI generation
    - Content validation
    - Telegram publishing
    - Database tracking
    - Approved group sharing
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        database: Optional[DatabaseInterface] = None,
        ai_generator: Optional[AIGenerator] = None,
        telegram_client: Optional[TelegramClient] = None,
    ):
        """
        Initialize publisher.

        Args:
            config: Config instance.
            database: Database implementation.
            ai_generator: AI generator instance.
            telegram_client: Telegram client instance.
        """
        self.config = config or get_config()

        self.database = database or create_database(self.config)
        self.ai = ai_generator or create_ai_generator(self.config)
        self.telegram = telegram_client or create_telegram_client(self.config)

        self.channel_id = self.config.telegram_channel_id

        logger.debug("Publisher initialized")

    # ============================================================
    # SAFETY
    # ============================================================

    def _publishing_blocked(self) -> bool:
        """
        Check whether publishing is currently blocked.

        Returns:
            True if emergency stop or maintenance mode is active.
        """
        if self.config.is_emergency_stopped():
            logger.warning("Emergency stop active. Publishing blocked.")
            return True

        if self.config.is_maintenance_mode():
            logger.warning("Maintenance mode active. Publishing blocked.")
            return True

        return False

    # ============================================================
    # LESSON ID
    # ============================================================

    def _make_lesson_id(
        self,
        month: str,
        day_number: int,
        lesson_type: str,
    ) -> str:
        """
        Generate a stable lesson ID.

        Args:
            month: Month identifier.
            day_number: Day number.
            lesson_type: Lesson type.

        Returns:
            Unique lesson ID string.
        """
        return generate_lesson_id(
            month,
            day_number,
            lesson_type,
        )

    # ============================================================
    # PUBLISH LESSON
    # ============================================================

    def publish_lesson(
        self,
        topic: str,
        lesson_type: str = "morning_lesson",
        month: str = "current",
        day_number: int = 0,
    ) -> Optional[Dict[str, Any]]:
        """
        Publish a lesson.

        Flow:
        1. Basic validation
        2. Safety check
        3. Idempotency check
        4. Generate content
        5. Validate content
        6. Send to Telegram
        7. Record in database

        Args:
            topic: Lesson topic.
            lesson_type: morning_lesson or evening_practice.
            month: Month identifier.
            day_number: Day number in curriculum.

        Returns:
            Telegram API response or None on failure.
        """
        logger.info(f"Publishing lesson: {topic} ({lesson_type})")

        # --------------------------------------------------------
        # Basic validation
        # --------------------------------------------------------

        if not topic or not topic.strip():
            logger.error("Cannot publish lesson with empty topic")
            return None

        if lesson_type not in (
            "morning_lesson",
            "evening_practice",
        ):
            logger.error(f"Invalid lesson type: {lesson_type}")
            return None

        # --------------------------------------------------------
        # Safety checks
        # --------------------------------------------------------

        if self._publishing_blocked():
            return None

        # --------------------------------------------------------
        # Generate lesson ID
        # --------------------------------------------------------

        lesson_id = self._make_lesson_id(
            month,
            day_number,
            lesson_type,
        )

        # --------------------------------------------------------
        # Idempotency check
        # --------------------------------------------------------

        try:
            existing = self.database.query_one(
                """
                SELECT id, status, telegram_message_id
                FROM lessons
                WHERE id = ?
                AND status = 'published'
                """,
                (lesson_id,),
            )

        except DatabaseError as e:
            logger.error(f"Database idempotency check failed: {e}")
            return None

        if existing:
            logger.warning(f"Lesson already published: {lesson_id}")
            return None

        # --------------------------------------------------------
        # AI generation
        # --------------------------------------------------------

        try:
            content = self.ai.generate_lesson(
                topic=topic,
                lesson_type=lesson_type,
            )

            logger.info(f"Content generated: {len(content)} characters")

        except AIGeneratorError as e:
            logger.error(f"AI generation failed for {lesson_id}: {e}")

            self._record_failure(
                lesson_id=lesson_id,
                month=month,
                day_number=day_number,
                lesson_type=lesson_type,
                topic=topic,
                error_msg=str(e),
            )

            return None

        except Exception as e:
            logger.exception(f"Unexpected AI generation error " f"for {lesson_id}")

            self._record_failure(
                lesson_id=lesson_id,
                month=month,
                day_number=day_number,
                lesson_type=lesson_type,
                topic=topic,
                error_msg=str(e),
            )

            return None

        # --------------------------------------------------------
        # Content validation
        # --------------------------------------------------------

        if not self.ai.validate_content(content):
            error_msg = "Generated content validation failed"

            logger.error(f"{error_msg}: {lesson_id}")

            self._record_failure(
                lesson_id=lesson_id,
                month=month,
                day_number=day_number,
                lesson_type=lesson_type,
                topic=topic,
                error_msg=error_msg,
            )

            return None

        # --------------------------------------------------------
        # Telegram publishing
        # --------------------------------------------------------

        try:
            result = self.telegram.send_message(
                chat_id=self.channel_id,
                text=content,
                parse_mode="HTML",
            )

            if not result:
                raise PublisherError("Telegram returned no response")

            telegram_result = result.get("result")

            if not isinstance(telegram_result, dict):
                raise PublisherError("Telegram response missing result object")

            message_id = telegram_result.get("message_id")

            if message_id is None:
                raise PublisherError("Telegram response missing message_id")

            logger.info(
                f"Lesson posted to channel. "
                f"lesson_id={lesson_id}, "
                f"message_id={message_id}"
            )

        except TelegramError as e:
            logger.error(f"Telegram publishing failed " f"for {lesson_id}: {e}")

            self._record_failure(
                lesson_id=lesson_id,
                month=month,
                day_number=day_number,
                lesson_type=lesson_type,
                topic=topic,
                error_msg=str(e),
            )

            return None

        except PublisherError as e:
            logger.error(f"Publisher error for {lesson_id}: {e}")

            self._record_failure(
                lesson_id=lesson_id,
                month=month,
                day_number=day_number,
                lesson_type=lesson_type,
                topic=topic,
                error_msg=str(e),
            )

            return None

        except Exception as e:
            logger.exception(f"Unexpected Telegram error " f"for {lesson_id}")

            self._record_failure(
                lesson_id=lesson_id,
                month=month,
                day_number=day_number,
                lesson_type=lesson_type,
                topic=topic,
                error_msg=str(e),
            )

            return None

        # --------------------------------------------------------
        # Database recording
        # --------------------------------------------------------

        try:
            published_at = get_current_timestamp()

            self.database.execute(
                """
                INSERT OR REPLACE INTO lessons
                (
                    id,
                    month,
                    day_number,
                    lesson_type,
                    topic,
                    content,
                    status,
                    telegram_message_id,
                    error_message,
                    published_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'published', ?, NULL, ?)
                """,
                (
                    lesson_id,
                    month,
                    day_number,
                    lesson_type,
                    topic,
                    content,
                    str(message_id),
                    published_at,
                ),
            )

            self.database.execute(
                """
                INSERT INTO published_posts
                (
                    lesson_id,
                    channel_message_id
                )
                VALUES (?, ?)
                """,
                (
                    lesson_id,
                    str(message_id),
                ),
            )

            logger.info(f"Lesson recorded successfully: {lesson_id}")

        except DatabaseError as e:
            # Telegram post already succeeded.
            # Do NOT pretend that publishing failed.
            logger.error(
                f"Telegram post succeeded but database "
                f"recording failed for {lesson_id}: {e}"
            )

        except Exception as e:
            logger.exception(
                f"Unexpected database recording error " f"for {lesson_id}: {e}"
            )

        return result

    # ============================================================
    # CUSTOM POST
    # ============================================================

    def publish_custom_post(
        self,
        text: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Publish a custom post to the configured channel.

        Args:
            text: Post content.

        Returns:
            Telegram API response or None.
        """
        logger.info("Publishing custom post")

        if self._publishing_blocked():
            return None

        if not text or not text.strip():
            logger.warning("Cannot publish empty custom post")
            return None

        try:
            result = self.telegram.send_message(
                chat_id=self.channel_id,
                text=text,
                parse_mode="HTML",
            )

            if not result:
                logger.error("Custom post failed: " "Telegram returned no response")
                return None

            telegram_result = result.get("result")

            if not isinstance(telegram_result, dict):
                logger.error("Custom post response missing result")
                return None

            message_id = telegram_result.get("message_id")

            if message_id is None:
                logger.error("Custom post response missing message_id")
                return None

            logger.info(f"Custom post published. " f"Message ID: {message_id}")

            return result

        except TelegramError as e:
            logger.error(f"Custom post failed: {e}")
            return None

        except Exception as e:
            logger.exception(f"Unexpected custom post error: {e}")
            return None

    # ============================================================
    # GROUP SHARING
    # ============================================================

    def share_to_approved_group(
        self,
        group_id: str,
        message_id: int,
    ) -> bool:
        """
        Share a channel post to an approved group.

        Checks:
        1. Group exists
        2. Group is approved
        3. Group is enabled
        4. Auto-share is enabled
        5. Forward message

        Args:
            group_id: Target group ID.
            message_id: Channel message ID.

        Returns:
            True if successful, otherwise False.
        """
        logger.info(
            f"Attempting group share: "
            f"message_id={message_id}, "
            f"group_id={group_id}"
        )

        if self._publishing_blocked():
            return False

        if not group_id:
            logger.error("Group ID is empty")
            return False

        if not message_id or message_id <= 0:
            logger.error(f"Invalid message ID: {message_id}")
            return False

        # --------------------------------------------------------
        # Check group approval/status
        # --------------------------------------------------------

        try:
            group = self.database.query_one(
                """
                SELECT *
                FROM groups
                WHERE group_id = ?
                AND status = 'approved'
                AND enabled = 1
                """,
                (group_id,),
            )

        except DatabaseError as e:
            logger.error(f"Database group check failed: {e}")
            return False

        if not group:
            logger.warning(f"Group not approved or disabled: {group_id}")
            return False

        # --------------------------------------------------------
        # Check auto-share
        # --------------------------------------------------------

        if not bool(group.get("auto_share")):
            logger.info(f"Auto-share disabled for group: {group_id}")
            return False

        # --------------------------------------------------------
        # Forward message
        # --------------------------------------------------------

        try:
            result = self.telegram.forward_message(
                from_chat_id=self.channel_id,
                message_id=message_id,
                to_chat_id=group_id,
            )

            if not result:
                logger.error(
                    f"Telegram returned no response " f"while sharing to {group_id}"
                )
                return False

            logger.info(
                f"Message {message_id} shared " f"successfully to group {group_id}"
            )

            return True

        except TelegramError as e:
            logger.error(
                f"Failed to share message {message_id} " f"to group {group_id}: {e}"
            )
            return False

        except Exception as e:
            logger.exception(f"Unexpected group share error " f"for {group_id}: {e}")
            return False

    # ============================================================
    # FAILURE RECORDING
    # ============================================================

    def _record_failure(
        self,
        lesson_id: str,
        month: str,
        day_number: int,
        lesson_type: str,
        topic: str,
        error_msg: str,
    ) -> None:
        """
        Record failed lesson in database.

        Failure recording must never crash the publisher.

        Args:
            lesson_id: Lesson ID.
            month: Month identifier.
            day_number: Day number.
            lesson_type: Lesson type.
            topic: Lesson topic.
            error_msg: Error message.
        """
        try:
            self.database.execute(
                """
                INSERT OR REPLACE INTO lessons
                (
                    id,
                    month,
                    day_number,
                    lesson_type,
                    topic,
                    status,
                    error_message
                )
                VALUES (?, ?, ?, ?, ?, 'failed', ?)
                """,
                (
                    lesson_id,
                    month,
                    day_number,
                    lesson_type,
                    topic,
                    error_msg,
                ),
            )

            logger.info(f"Failure recorded: {lesson_id}")

        except DatabaseError as e:
            logger.error(f"Failed to record lesson failure " f"{lesson_id}: {e}")

        except Exception as e:
            logger.exception(
                f"Unexpected failure-recording error " f"for {lesson_id}: {e}"
            )

    # ============================================================
    # CLOSE
    # ============================================================

    def close(self) -> None:
        """
        Close publisher database connection.

        Safe to call multiple times.
        """
        if self.database:
            try:
                self.database.close()
                logger.debug("Publisher database connection closed")
            except Exception as e:
                logger.error(f"Failed to close database: {e}")


# ================================================================
# FACTORY
# ================================================================


def create_publisher(
    config: Optional[Config] = None,
) -> Publisher:
    """
    Factory function for Publisher.

    Args:
        config: Optional Config instance.

    Returns:
        Publisher instance.
    """
    return Publisher(config=config)
