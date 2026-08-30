# modules/group_manager.py
"""
Group Manager for AI Teacher Bot.

Part 4 - Group Management & Distribution

Responsibilities:
- Register / get / list Telegram groups
- Approve / reject / remove groups
- Enable / disable groups and auto-share
- Enforce daily share limits
- Prevent duplicate lesson sharing
- Record shares and track history

Safety:
- No automatic group joining
- No member scraping
- No message scraping
- Only approved + enabled + auto_share groups receive content
"""

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from database import DatabaseInterface, DatabaseError

logger = logging.getLogger(__name__)


# ============================================================
# EXCEPTIONS
# ============================================================


class GroupManagerError(Exception):
    """Base exception for group manager."""

    pass


class GroupNotFoundError(GroupManagerError):
    """Raised when a group does not exist."""

    pass


class GroupNotApprovedError(GroupManagerError):
    """Raised when a group is not approved."""

    pass


class GroupDisabledError(GroupManagerError):
    """Raised when a group is disabled."""

    pass


class AutoShareDisabledError(GroupManagerError):
    """Raised when auto-share is disabled."""

    pass


class ShareLimitExceededError(GroupManagerError):
    """Raised when daily share limit is exceeded."""

    pass


class DuplicateShareError(GroupManagerError):
    """Raised when lesson was already shared to group."""

    pass


# ============================================================
# GROUP MANAGER
# ============================================================


class GroupManager:
    """
    Manage Telegram groups for content distribution.

    Sharing is allowed only when ALL conditions are met:
        1. Group exists
        2. status == 'approved'
        3. enabled == 1
        4. auto_share == 1
        5. Daily share limit not exceeded
        6. Lesson has not already been shared
    """

    def __init__(
        self,
        database: DatabaseInterface,
        max_daily_shares: int = 2,
    ):
        if max_daily_shares < 1:
            raise ValueError("max_daily_shares must be at least 1")

        self.database = database
        self.max_daily_shares = max_daily_shares

        logger.info(
            f"GroupManager initialized " f"(max_daily_shares={max_daily_shares})"
        )

    # ========================================================
    # DATABASE HELPERS
    # ========================================================

    def _execute(
        self,
        sql: str,
        params: tuple = (),
    ) -> bool:
        """Execute a write query safely."""
        try:
            self.database.execute(sql, params)
            return True
        except DatabaseError as exc:
            logger.error(f"Database error: {exc}")
            return False

    # ========================================================
    # REGISTRATION & GETTERS
    # ========================================================

    def register_group(
        self,
        group_id: str,
        group_title: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Register a new group. Starts as pending with auto_share off."""
        group_id = (group_id or "").strip()

        if not group_id:
            logger.error("Cannot register empty group ID")
            return None

        existing = self.get_group(group_id)
        if existing:
            logger.info(f"Group already registered: {group_id}")
            return existing

        success = self._execute(
            """
            INSERT INTO groups
            (group_id, group_title, status, auto_share, enabled)
            VALUES (?, ?, 'pending', 0, 1)
            """,
            (group_id, group_title),
        )

        if success:
            logger.info(f"Group registered: {group_id}")
            return self.get_group(group_id)

        return None

    def get_group(self, group_id: str) -> Optional[Dict[str, Any]]:
        """Get one group by Telegram group ID."""
        try:
            return self.database.query_one(
                "SELECT * FROM groups WHERE group_id = ?",
                (group_id,),
            )
        except DatabaseError as exc:
            logger.error(f"Failed to get group {group_id}: {exc}")
            return None

    def get_all_groups(
        self,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get all groups, optionally filtered by status."""
        try:
            if status:
                return self.database.query(
                    "SELECT * FROM groups WHERE status = ? ORDER BY added_date ASC",
                    (status,),
                )
            return self.database.query("SELECT * FROM groups ORDER BY added_date ASC")
        except DatabaseError as exc:
            logger.error(f"Failed to get groups: {exc}")
            return []

    def get_approved_groups(self) -> List[Dict[str, Any]]:
        """Get approved + enabled + auto_share groups."""
        try:
            return self.database.query("""
                SELECT * FROM groups
                WHERE status = 'approved'
                  AND enabled = 1
                  AND auto_share = 1
                ORDER BY added_date ASC
                """)
        except DatabaseError as exc:
            logger.error(f"Failed to get approved groups: {exc}")
            return []

    # ========================================================
    # STATUS UPDATES
    # ========================================================

    def approve_group(self, group_id: str) -> bool:
        """Approve a group."""
        if not self.get_group(group_id):
            logger.warning(f"Cannot approve missing group: {group_id}")
            return False

        if self._execute(
            "UPDATE groups SET status = 'approved' WHERE group_id = ?",
            (group_id,),
        ):
            logger.info(f"Group approved: {group_id}")
            return True
        return False

    def reject_group(self, group_id: str) -> bool:
        """Reject and disable a group."""
        if not self.get_group(group_id):
            logger.warning(f"Cannot reject missing group: {group_id}")
            return False

        if self._execute(
            """
            UPDATE groups
            SET status = 'rejected', enabled = 0, auto_share = 0
            WHERE group_id = ?
            """,
            (group_id,),
        ):
            logger.info(f"Group rejected: {group_id}")
            return True
        return False

    def remove_group(self, group_id: str) -> bool:
        """Remove a group from database."""
        if not self.get_group(group_id):
            logger.warning(f"Group not found: {group_id}")
            return False

        if self._execute(
            "DELETE FROM groups WHERE group_id = ?",
            (group_id,),
        ):
            logger.info(f"Group removed: {group_id}")
            return True
        return False

    def enable_group(self, group_id: str) -> bool:
        """Enable group."""
        if self._execute(
            "UPDATE groups SET enabled = 1 WHERE group_id = ?",
            (group_id,),
        ):
            logger.info(f"Group enabled: {group_id}")
            return True
        return False

    def disable_group(self, group_id: str) -> bool:
        """Disable group without deleting."""
        if self._execute(
            "UPDATE groups SET enabled = 0 WHERE group_id = ?",
            (group_id,),
        ):
            logger.info(f"Group disabled: {group_id}")
            return True
        return False

    def enable_auto_share(self, group_id: str) -> bool:
        """Enable auto-share. Group must already be approved."""
        group = self.get_group(group_id)

        if not group:
            return False

        if group.get("status") != "approved":
            logger.warning(f"Cannot enable auto-share for unapproved group: {group_id}")
            return False

        if self._execute(
            "UPDATE groups SET auto_share = 1 WHERE group_id = ?",
            (group_id,),
        ):
            logger.info(f"Auto-share enabled: {group_id}")
            return True
        return False

    def disable_auto_share(self, group_id: str) -> bool:
        """Disable auto-share."""
        if self._execute(
            "UPDATE groups SET auto_share = 0 WHERE group_id = ?",
            (group_id,),
        ):
            logger.info(f"Auto-share disabled: {group_id}")
            return True
        return False

    # ========================================================
    # SHARE VALIDATION HELPERS
    # ========================================================

    def _get_effective_daily_count(
        self,
        group: Dict[str, Any],
    ) -> int:
        """Get today's effective share count."""
        today = date.today().isoformat()
        last_share_date = group.get("last_share_date")
        daily_count = int(group.get("daily_share_count") or 0)

        if last_share_date != today:
            return 0
        return daily_count

    def check_share_allowed(self, group_id: str) -> bool:
        """Check if group can receive a share. Returns bool."""
        group = self.get_group(group_id)

        if not group:
            return False
        if group.get("status") != "approved":
            return False
        if not bool(group.get("enabled")):
            return False
        if not bool(group.get("auto_share")):
            return False

        if self._get_effective_daily_count(group) >= self.max_daily_shares:
            return False

        return True

    def validate_share(
        self,
        group_id: str,
        lesson_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Validate share. Raises specific exceptions on failure."""
        group = self.get_group(group_id)

        if not group:
            raise GroupNotFoundError(f"Group not found: {group_id}")
        if group.get("status") != "approved":
            raise GroupNotApprovedError(f"Group not approved: {group_id}")
        if not bool(group.get("enabled")):
            raise GroupDisabledError(f"Group disabled: {group_id}")
        if not bool(group.get("auto_share")):
            raise AutoShareDisabledError(f"Auto-share disabled: {group_id}")

        daily_count = self._get_effective_daily_count(group)

        if daily_count >= self.max_daily_shares:
            raise ShareLimitExceededError(
                f"Daily share limit: {group_id} "
                f"({daily_count}/{self.max_daily_shares})"
            )

        if lesson_id and self.has_shared(lesson_id, group_id):
            raise DuplicateShareError(
                f"Lesson already shared: {lesson_id} -> {group_id}"
            )

        return {
            "allowed": True,
            "group": group,
            "daily_share_count": daily_count,
            "daily_share_limit": self.max_daily_shares,
        }

    # ========================================================
    # SHARE RECORDING & HISTORY
    # ========================================================

    def record_share(
        self,
        group_id: str,
        lesson_id: str,
        channel_message_id: str,
        group_message_id: Optional[str] = None,
    ) -> bool:
        """Record a successful share and update counters."""
        try:
            self.validate_share(group_id=group_id, lesson_id=lesson_id)

            # Insert share history
            self.database.execute(
                """
                INSERT INTO shared_posts
                (lesson_id, channel_message_id, group_id, group_message_id, status)
                VALUES (?, ?, ?, ?, 'shared')
                """,
                (lesson_id, channel_message_id, group_id, group_message_id),
            )

            # Update counters
            today = date.today().isoformat()
            group = self.get_group(group_id)

            if not group:
                raise GroupNotFoundError(f"Group disappeared: {group_id}")

            daily_count = self._get_effective_daily_count(group)

            if daily_count > 0:
                self.database.execute(
                    """
                    UPDATE groups
                    SET daily_share_count = daily_share_count + 1,
                        total_shares = COALESCE(total_shares, 0) + 1,
                        last_share_date = ?
                    WHERE group_id = ?
                    """,
                    (today, group_id),
                )
            else:
                self.database.execute(
                    """
                    UPDATE groups
                    SET daily_share_count = 1,
                        total_shares = COALESCE(total_shares, 0) + 1,
                        last_share_date = ?
                    WHERE group_id = ?
                    """,
                    (today, group_id),
                )

            logger.info(f"Share recorded: {lesson_id} -> {group_id}")
            return True

        except DuplicateShareError:
            logger.warning(f"Duplicate share blocked: {lesson_id} -> {group_id}")
            return False
        except GroupManagerError as exc:
            logger.warning(f"Share blocked: {exc}")
            return False
        except DatabaseError as exc:
            logger.error(f"Database error recording share: {exc}")
            return False

    def has_shared(self, lesson_id: str, group_id: str) -> bool:
        """Check if lesson already shared to group."""
        try:
            result = self.database.query_one(
                "SELECT id FROM shared_posts WHERE lesson_id = ? AND group_id = ? LIMIT 1",
                (lesson_id, group_id),
            )
            return result is not None
        except DatabaseError as exc:
            logger.error(f"Failed to check share history: {exc}")
            return False

    def get_share_history(
        self,
        group_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get share history."""
        try:
            if group_id:
                return self.database.query(
                    """
                    SELECT * FROM shared_posts
                    WHERE group_id = ?
                    ORDER BY shared_at DESC
                    LIMIT ?
                    """,
                    (group_id, limit),
                )
            return self.database.query(
                "SELECT * FROM shared_posts ORDER BY shared_at DESC LIMIT ?",
                (limit,),
            )
        except DatabaseError as exc:
            logger.error(f"Failed to get share history: {exc}")
            return []

    def reset_daily_share_counts(self) -> None:
        """Reset daily share counts."""
        self._execute("UPDATE groups SET daily_share_count = 0")

    def get_share_stats(self) -> Dict[str, Any]:
        """Get overall share statistics."""
        try:
            total_shares = self.database.query_one(
                "SELECT COALESCE(SUM(total_shares), 0) AS total FROM groups"
            )
            total_groups = self.database.query_one(
                "SELECT COUNT(*) AS count FROM groups"
            )
            approved_groups = self.database.query_one("""
                SELECT COUNT(*) AS count FROM groups
                WHERE status = 'approved' AND enabled = 1
                """)

            return {
                "total_shares": int((total_shares or {}).get("total", 0)),
                "total_groups": int((total_groups or {}).get("count", 0)),
                "approved_groups": int((approved_groups or {}).get("count", 0)),
            }
        except DatabaseError as exc:
            logger.error(f"Failed to get share stats: {exc}")
            return {"total_shares": 0, "total_groups": 0, "approved_groups": 0}


# ============================================================
# FACTORY
# ============================================================


def create_group_manager(
    database: DatabaseInterface,
    max_daily_shares: int = 2,
) -> GroupManager:
    """Factory function for GroupManager."""
    return GroupManager(
        database=database,
        max_daily_shares=max_daily_shares,
    )
