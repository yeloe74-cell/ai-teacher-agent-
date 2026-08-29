# modules/share_distributor.py
"""
Share Distributor for AI Teacher Bot.

Part 4 - Group Management & Distribution.

Responsibilities:
- Distribute channel posts to approved groups
- Respect auto-share settings and daily limits
- Prevent duplicate sharing
- Forward messages safely
- Record successful shares
- Continue distribution if one group fails
- Return detailed distribution results

Safety:
- Never auto-joins groups
- Never scrapes groups
- Only distributes to registered/approved groups
"""

import logging
from typing import Any, Dict, Optional

from database import DatabaseInterface
from modules.group_manager import GroupManager
from modules.telegram_client import TelegramClient


logger = logging.getLogger(__name__)


# ============================================================
# EXCEPTIONS
# ============================================================

class ShareDistributorError(Exception):
    """Base exception for share distributor."""
    pass


class ShareForwardError(ShareDistributorError):
    """Raised when Telegram forwarding fails."""
    pass


class ShareRecordError(ShareDistributorError):
    """Raised when share recording fails."""
    pass


# ============================================================
# SHARE DISTRIBUTOR
# ============================================================

class ShareDistributor:
    """
    Distributes channel posts to approved Telegram groups.

    Flow:

        Channel Post
             ↓
        Approved Group
             ↓
        Validate Group
             ↓
        Check Duplicate
             ↓
        Forward Message
             ↓
        Record Share
             ↓
        Update Counters

    Important:
        A failure in one group will not stop distribution
        to other groups.
    """

    def __init__(
        self,
        database: DatabaseInterface,
        telegram_client: TelegramClient,
        group_manager: GroupManager,
        channel_id: str,
    ):
        """
        Initialize ShareDistributor.

        Args:
            database:
                Database interface.

            telegram_client:
                Telegram API client.

            group_manager:
                Group management service.

            channel_id:
                Source Telegram channel ID.
        """
        self.database = database
        self.telegram = telegram_client
        self.groups = group_manager
        self.channel_id = str(channel_id).strip()

        if not self.channel_id:
            raise ValueError("channel_id cannot be empty")

        logger.info(
            f"ShareDistributor initialized "
            f"(channel_id={self.channel_id})"
        )

    # ========================================================
    # INPUT VALIDATION
    # ========================================================

    @staticmethod
    def _validate_inputs(
        group_id: Any,
        lesson_id: Any,
        message_id: Any,
    ) -> bool:
        """Validate required distribution inputs."""

        if not group_id or not str(group_id).strip():
            logger.warning("Distribution rejected: empty group_id")
            return False

        if not lesson_id or not str(lesson_id).strip():
            logger.warning("Distribution rejected: empty lesson_id")
            return False

        if message_id is None:
            logger.warning(
                f"Distribution rejected: empty message_id "
                f"(lesson={lesson_id})"
            )
            return False

        return True

    @staticmethod
    def _safe_int(value: Any) -> Optional[int]:
        """Safely convert a value to integer."""

        try:
            result = int(value)

            if result <= 0:
                logger.error(
                    f"Invalid message_id: {value}"
                )
                return None

            return result

        except (ValueError, TypeError):
            logger.error(
                f"Invalid message_id: {value}"
            )
            return None

    # ========================================================
    # MESSAGE ID EXTRACTION
    # ========================================================

    @staticmethod
    def _extract_message_id(
        result: Any,
    ) -> Optional[str]:
        """
        Extract message_id from Telegram response.

        Supports:

        {
            "ok": True,
            "result": {
                "message_id": 123
            }
        }

        and:

        {
            "message_id": 123
        }
        """

        if not isinstance(result, dict):
            return None

        # Standard Telegram Bot API response
        nested_result = result.get("result")

        if isinstance(nested_result, dict):
            message_id = nested_result.get("message_id")

            if message_id is not None:
                return str(message_id)

        # Direct response
        message_id = result.get("message_id")

        if message_id is not None:
            return str(message_id)

        return None

    # ========================================================
    # SINGLE GROUP DISTRIBUTION
    # ========================================================

    def distribute_to_group(
        self,
        group_id: str,
        message_id: int,
        lesson_id: str,
    ) -> Dict[str, Any]:
        """
        Distribute one channel message to one group.

        Returns:
            {
                "success": bool,
                "status": "shared" | "skipped" | "failed",
                "group_id": str,
                "lesson_id": str,
                "reason": Optional[str],
                "group_message_id": Optional[str]
            }
        """

        result: Dict[str, Any] = {
            "success": False,
            "status": "failed",
            "group_id": str(group_id or "").strip(),
            "lesson_id": str(lesson_id or "").strip(),
            "reason": None,
            "group_message_id": None,
        }

        # ----------------------------------------------------
        # Validate inputs
        # ----------------------------------------------------

        if not self._validate_inputs(
            group_id,
            lesson_id,
            message_id,
        ):
            result["status"] = "failed"
            result["reason"] = "invalid_input"
            return result

        group_id = str(group_id).strip()
        lesson_id = str(lesson_id).strip()

        result["group_id"] = group_id
        result["lesson_id"] = lesson_id

        # ----------------------------------------------------
        # Check group permission
        # ----------------------------------------------------

        try:
            allowed = self.groups.check_share_allowed(
                group_id
            )

        except Exception as exc:
            logger.error(
                f"Failed share permission check "
                f"for {group_id}: {exc}"
            )

            result["status"] = "failed"
            result["reason"] = "permission_check_error"
            return result

        if not allowed:
            logger.info(
                f"Share skipped: group not allowed "
                f"({group_id})"
            )

            result["status"] = "skipped"
            result["reason"] = "share_not_allowed"
            return result

        # ----------------------------------------------------
        # Duplicate protection
        # ----------------------------------------------------

        try:
            already_shared = self.groups.has_shared(
                lesson_id=lesson_id,
                group_id=group_id,
            )

        except Exception as exc:
            logger.error(
                f"Duplicate check failed "
                f"{lesson_id} -> {group_id}: {exc}"
            )

            result["status"] = "failed"
            result["reason"] = "duplicate_check_error"
            return result

        if already_shared:
            logger.info(
                f"Share skipped: already shared "
                f"{lesson_id} -> {group_id}"
            )

            result["status"] = "skipped"
            result["reason"] = "already_shared"
            return result

        # ----------------------------------------------------
        # Validate message ID
        # ----------------------------------------------------

        message_id_int = self._safe_int(message_id)

        if message_id_int is None:
            result["status"] = "failed"
            result["reason"] = "invalid_message_id"
            return result

        # ----------------------------------------------------
        # Forward Telegram message
        # ----------------------------------------------------

        try:
            telegram_result = self.telegram.forward_message(
                from_chat_id=self.channel_id,
                message_id=message_id_int,
                to_chat_id=group_id,
            )

        except Exception as exc:
            logger.error(
                f"Telegram forwarding exception "
                f"{lesson_id} -> {group_id}: {exc}"
            )

            result["status"] = "failed"
            result["reason"] = "telegram_forward_error"
            result["error"] = str(exc)
            return result

        # ----------------------------------------------------
        # Validate Telegram response
        # ----------------------------------------------------

        if not telegram_result:
            logger.error(
                f"Telegram forwarding failed "
                f"{lesson_id} -> {group_id}"
            )

            result["status"] = "failed"
            result["reason"] = "telegram_forward_failed"
            return result

        group_message_id = self._extract_message_id(
            telegram_result
        )

        if not group_message_id:
            logger.error(
                f"Forward response missing message_id "
                f"{lesson_id} -> {group_id}"
            )

            result["status"] = "failed"
            result["reason"] = "missing_group_message_id"
            return result

        result["group_message_id"] = group_message_id

        # ----------------------------------------------------
        # Record successful share
        # ----------------------------------------------------

        try:
            recorded = self.groups.record_share(
                group_id=group_id,
                lesson_id=lesson_id,
                channel_message_id=str(message_id_int),
                group_message_id=group_message_id,
            )

        except Exception as exc:
            logger.error(
                f"Share record exception "
                f"{lesson_id} -> {group_id}: {exc}"
            )

            result["status"] = "failed"
            result["reason"] = "share_record_error"
            result["error"] = str(exc)
            return result

        if not recorded:
            logger.error(
                f"Message forwarded but database record failed "
                f"{lesson_id} -> {group_id}"
            )

            result["status"] = "failed"
            result["reason"] = "share_record_failed"
            return result

        # ----------------------------------------------------
        # Success
        # ----------------------------------------------------

        result["success"] = True
        result["status"] = "shared"
        result["reason"] = "success"

        logger.info(
            f"✅ Shared successfully "
            f"{lesson_id} -> {group_id}"
        )

        return result

    # ========================================================
    # DISTRIBUTE TO ALL APPROVED GROUPS
    # ========================================================

    def distribute_to_all_approved(
        self,
        message_id: int,
        lesson_id: str,
    ) -> Dict[str, Any]:
        """
        Distribute a channel post to all approved groups.

        One group failure will NOT stop other groups.

        Returns:

            {
                "success": True,
                "total_groups": 3,
                "shared": 2,
                "skipped": 1,
                "failed": 0,
                "details": [...]
            }
        """

        summary: Dict[str, Any] = {
            "success": True,
            "total_groups": 0,
            "shared": 0,
            "skipped": 0,
            "failed": 0,
            "details": [],
        }

        # ----------------------------------------------------
        # Validate global inputs
        # ----------------------------------------------------

        if self._safe_int(message_id) is None:
            logger.error(
                "Distribution aborted: invalid message_id"
            )

            summary["success"] = False
            summary["error"] = "invalid_message_id"
            return summary

        if not lesson_id or not str(lesson_id).strip():
            logger.error(
                "Distribution aborted: empty lesson_id"
            )

            summary["success"] = False
            summary["error"] = "invalid_lesson_id"
            return summary

        lesson_id = str(lesson_id).strip()

        # ----------------------------------------------------
        # Get approved groups
        # ----------------------------------------------------

        try:
            approved_groups = (
                self.groups.get_approved_groups()
            )

        except Exception as exc:
            logger.error(
                f"Failed to get approved groups: {exc}"
            )

            summary["success"] = False
            summary["error"] = "approved_groups_error"
            return summary

        if not approved_groups:
            logger.info(
                "No approved auto-share groups available."
            )
            return summary

        summary["total_groups"] = len(
            approved_groups
        )

        logger.info(
            f"Starting distribution: "
            f"lesson={lesson_id}, "
            f"message={message_id}, "
            f"groups={len(approved_groups)}"
        )

        # ----------------------------------------------------
        # Process every group independently
        # ----------------------------------------------------

        for group in approved_groups:

            group_id = group.get("group_id")

            if not group_id:
                summary["skipped"] += 1

                summary["details"].append({
                    "group_id": None,
                    "status": "skipped",
                    "reason": "missing_group_id",
                })

                logger.warning(
                    "Skipping group with missing group_id"
                )

                continue

            group_id = str(group_id).strip()

            # ------------------------------------------------
            # Distribute
            # ------------------------------------------------

            try:
                share_result = (
                    self.distribute_to_group(
                        group_id=group_id,
                        message_id=message_id,
                        lesson_id=lesson_id,
                    )
                )

            except Exception as exc:
                logger.exception(
                    f"Unexpected distribution error "
                    f"for {group_id}: {exc}"
                )

                summary["failed"] += 1

                summary["details"].append({
                    "group_id": group_id,
                    "status": "failed",
                    "reason": "unexpected_error",
                    "error": str(exc),
                })

                continue

            # ------------------------------------------------
            # Process result
            # ------------------------------------------------

            status = share_result.get(
                "status",
                "failed",
            )

            if status == "shared":

                summary["shared"] += 1

                summary["details"].append(
                    share_result
                )

            elif status == "skipped":

                summary["skipped"] += 1

                summary["details"].append(
                    share_result
                )

            else:

                summary["failed"] += 1

                summary["details"].append(
                    share_result
                )

        # ----------------------------------------------------
        # Final result
        # ----------------------------------------------------

        if summary["failed"] > 0:
            summary["success"] = False

        logger.info(
            "Distribution complete: "
            f"total={summary['total_groups']}, "
            f"shared={summary['shared']}, "
            f"skipped={summary['skipped']}, "
            f"failed={summary['failed']}"
        )

        return summary


# ============================================================
# FACTORY
# ============================================================

def create_share_distributor(
    database: DatabaseInterface,
    telegram_client: TelegramClient,
    group_manager: GroupManager,
    channel_id: str,
) -> ShareDistributor:
    """
    Factory function for ShareDistributor.

    Returns:
        Configured ShareDistributor instance.
    """

    return ShareDistributor(
        database=database,
        telegram_client=telegram_client,
        group_manager=group_manager,
        channel_id=channel_id,
      )
