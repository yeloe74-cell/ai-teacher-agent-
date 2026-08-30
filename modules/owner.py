# modules/owner.py
"""
Owner Command Handler for AI Teacher Bot.

Owner only:
- status, pause, resume
- groups, grouplist, approve, remove
- global, broadcast, post, forcepost, share
- editpost, deletepost
- scan, links, join, joinall, reject, clearlinks
- ban, unban, kick, pin, unpin
- settime, setmonth, scheduled, skipday, resetday
- stats, lessonstatus, agentstatus, uptime
- backup, clearlogs, restart
- proposals, feedback
- help
"""

import logging
import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import Config, get_config
from database import DatabaseInterface
from modules.group_manager import GroupManager
from modules.telegram_client import TelegramClient
from modules.owner_extra import OwnerExtra

logger = logging.getLogger(__name__)


class OwnerHandler:
    """Handles Owner-only Telegram commands."""

    LINK_PATTERNS = (
        r"https?://t\.me/([a-zA-Z0-9_]+)",
        r"https?://telegram\.me/([a-zA-Z0-9_]+)",
        r"@([a-zA-Z0-9_]+)",
    )

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
        self.owner_id = str(self.config.owner_user_id)

        logger.info("OwnerHandler initialized")

    # ========================================================
    # HELPERS
    # ========================================================

    def is_owner(self, user_id: Any) -> bool:
        return str(user_id) == self.owner_id

    def _send(self, chat_id: Any, text: str) -> None:
        if not self.telegram:
            return

        try:
            self.telegram.send_message(
                chat_id=str(chat_id),
                text=text,
                parse_mode="HTML",
            )
        except Exception as exc:
            logger.error("Send failed: %s", exc)

    def _set_state(self, key: str, value: str) -> bool:
        if not self.database:
            return False

        try:
            self.database.execute(
                """
                INSERT OR REPLACE INTO app_state
                (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                """,
                (key, value),
            )
            return True
        except Exception as exc:
            logger.error("State set failed: %s", exc)
            return False

    def _get_state(self, key: str, default: str = "") -> str:
        if not self.database:
            return default

        try:
            row = self.database.query_one(
                "SELECT value FROM app_state WHERE key=?",
                (key,),
            )
            return str(row.get("value", default)) if row else default
        except Exception:
            return default

    # ========================================================
    # MESSAGE HANDLER
    # ========================================================

    def handle_message(self, update: Dict[str, Any]) -> bool:
        """Process Owner commands only."""

        try:
            message = update.get("message")
            if not message:
                return False

            user_id = message.get("from", {}).get("id")

            if not self.is_owner(user_id):
                return False

            text = (message.get("text") or "").strip()
            chat_id = message.get("chat", {}).get("id")

            if not text.startswith("/"):
                return False

            self._dispatch(text, chat_id)
            return True

        except Exception:
            logger.exception("Owner message handling failed")
            return False

    # ========================================================
    # DISPATCH
    # ========================================================

    def _dispatch(self, text: str, chat_id: Any) -> None:
        parts = text.split()
        if not parts:
            return

        command = parts[0].lower().split("@", 1)[0]
        args = parts[1:]

        commands = {
            # Basic
            "/status": lambda: self.cmd_status(chat_id),
            "/pause": lambda: self.cmd_pause(chat_id),
            "/resume": lambda: self.cmd_resume(chat_id),

            # Groups
            "/groups": lambda: self.cmd_groups(chat_id),
            "/grouplist": lambda: self.cmd_grouplist(chat_id),
            "/approve": lambda: self.cmd_approve(chat_id, args),
            "/remove": lambda: self.cmd_remove(chat_id, args),

            # Posting
            "/global": lambda: self.cmd_global(chat_id, args),
            "/broadcast": lambda: self.cmd_broadcast(chat_id, args),
            "/post": lambda: self.cmd_post(chat_id, args),
            "/forcepost": lambda: self.cmd_post(chat_id, args),
            "/share": lambda: self.cmd_share(chat_id, args),
            "/editpost": lambda: self.cmd_editpost(chat_id, args),
            "/deletepost": lambda: self.cmd_deletepost(chat_id, args),

            # Links
            "/scan": lambda: self.cmd_scan(chat_id),
            "/links": lambda: self.cmd_scan(chat_id),
            "/join": lambda: self.cmd_join(chat_id, args),
            "/joinall": lambda: self.cmd_joinall(chat_id),
            "/reject": lambda: self.cmd_reject(chat_id, args),
            "/clearlinks": lambda: self.cmd_clearlinks(chat_id),

            # Moderation
            "/ban": lambda: self.cmd_mod(chat_id, args, "banChatMember"),
            "/unban": lambda: self.cmd_mod(chat_id, args, "unbanChatMember"),
            "/kick": lambda: self.cmd_kick(chat_id, args),
            "/pin": lambda: self.cmd_pin(chat_id, args),
            "/unpin": lambda: self.cmd_unpin(chat_id),

            # Schedule
            "/settime": lambda: self.cmd_settime(chat_id, args),
            "/setmonth": lambda: self.cmd_setmonth(chat_id, args),
            "/scheduled": lambda: self.cmd_scheduled(chat_id),
            "/skipday": lambda: self.cmd_skipday(chat_id),
            "/resetday": lambda: self.cmd_resetday(chat_id, args),

            # Stats
            "/stats": lambda: self.cmd_stats(chat_id),
            "/lessonstatus": lambda: self.cmd_lessonstatus(chat_id),
            "/agentstatus": lambda: self.cmd_agentstatus(chat_id),
            "/uptime": lambda: self.cmd_uptime(chat_id),

            # Maintenance
            "/backup": lambda: self.cmd_backup(chat_id),
            "/clearlogs": lambda: self.cmd_clearlogs(chat_id),
            "/restart": lambda: self.cmd_restart(chat_id),

            # AI
            "/proposals": lambda: self.cmd_proposals(chat_id),
            "/feedback": lambda: self.cmd_feedback(chat_id),

            # Help
            "/help": lambda: self.cmd_help(chat_id),
        }

        handler = commands.get(command)

        if not handler:
            self._send(chat_id, f"❌ Unknown command: {command}")
            return

        try:
            handler()
        except Exception as exc:
            logger.exception("Command failed: %s", command)
            self._send(chat_id, f"❌ Error: {exc}")

    # ========================================================
    # BASIC
    # ========================================================

    def cmd_status(self, chat_id: Any) -> None:
        paused = self._get_state("paused", "0") == "1"
        state = "⏸️ PAUSED" if paused else "▶️ RUNNING"

        count = 0
        if self.groups:
            count = len(self.groups.get_approved_groups())

        self._send(
            chat_id,
            f"<b>🤖 AI Teacher Bot</b>\n"
            f"Status: {state}\n"
            f"Groups: {count}",
        )

    def cmd_pause(self, chat_id: Any) -> None:
        self._set_state("paused", "1")
        self._send(chat_id, "⏸️ Publishing paused.")

    def cmd_resume(self, chat_id: Any) -> None:
        self._set_state("paused", "0")
        self._send(chat_id, "▶️ Publishing resumed.")

    # ========================================================
    # GROUPS
    # ========================================================

    def cmd_groups(self, chat_id: Any) -> None:
        if not self.groups:
            self._send(chat_id, "❌ Group manager unavailable.")
            return

        groups = self.groups.get_approved_groups()

        if not groups:
            self._send(chat_id, "No approved groups.")
            return

        lines = ["<b>👥 Approved Groups</b>"]

        for group in groups:
            gid = group.get("group_id", "?")
            shares = group.get("total_shares", 0)
            lines.append(f"• {gid} | {shares} shares")

        self._send(chat_id, "\n".join(lines))

    def cmd_grouplist(self, chat_id: Any) -> None:
        """Show all groups by status."""
        if not self.groups:
            self._send(chat_id, "❌ Group manager unavailable.")
            return

        groups = self.groups.get_all_groups()

        if not groups:
            self._send(chat_id, "No groups registered.")
            return

        pending = [g for g in groups if g.get("status") == "pending"]
        approved = [g for g in groups if g.get("status") == "approved"]
        rejected = [g for g in groups if g.get("status") == "rejected"]

        lines = ["<b>📋 All Groups</b>"]

        lines.append(f"\n✅ Approved ({len(approved)}):")
        for g in approved:
            lines.append(f"• {g.get('group_id', '?')}")

        lines.append(f"\n⏳ Pending ({len(pending)}):")
        for g in pending:
            lines.append(f"• {g.get('group_id', '?')}")

        lines.append(f"\n❌ Rejected ({len(rejected)}):")
        for g in rejected:
            lines.append(f"• {g.get('group_id', '?')}")

        self._send(chat_id, "\n".join(lines))

    def cmd_approve(self, chat_id: Any, args: List[str]) -> None:
        if not args:
            self._send(chat_id, "Usage: /approve @group")
            return

        if not self.groups:
            self._send(chat_id, "❌ Group manager unavailable.")
            return

        ok = self.groups.approve_group(args[0])
        self._send(chat_id, "✅ Approved" if ok else "❌ Failed")

    def cmd_remove(self, chat_id: Any, args: List[str]) -> None:
        if not args:
            self._send(chat_id, "Usage: /remove @group")
            return

        if not self.groups:
            self._send(chat_id, "❌ Group manager unavailable.")
            return

        ok = self.groups.remove_group(args[0])
        self._send(chat_id, "✅ Removed" if ok else "❌ Failed")

    # ========================================================
    # BROADCAST
    # ========================================================

    def cmd_global(self, chat_id: Any, args: List[str]) -> None:
        """Broadcast to approved groups."""
        if not args:
            self._send(chat_id, "Usage: /global message")
            return

        if not self.telegram or not self.groups:
            self._send(chat_id, "❌ Not available.")
            return

        groups = self.groups.get_approved_groups()

        if not groups:
            self._send(chat_id, "No approved groups.")
            return

        text = " ".join(args)
        success = 0
        failed = 0

        for group in groups:
            group_id = group.get("group_id")

            if not group_id:
                failed += 1
                continue

            try:
                self.telegram.send_message(
                    chat_id=str(group_id),
                    text=text,
                    parse_mode="HTML",
                )
                success += 1
            except Exception as exc:
                logger.error("Broadcast failed %s: %s", group_id, exc)
                failed += 1

        self._send(
            chat_id,
            f"📢 <b>Global Broadcast</b>\n"
            f"✅ Sent: {success}\n"
            f"❌ Failed: {failed}\n"
            f"📊 Total: {len(groups)}",
        )

    def cmd_broadcast(self, chat_id: Any, args: List[str]) -> None:
        """Broadcast to ALL enabled groups (not just auto_share)."""
        if not args:
            self._send(chat_id, "Usage: /broadcast message")
            return

        if not self.telegram or not self.groups:
            self._send(chat_id, "❌ Not available")
            return

        groups = self.groups.get_all_enabled_groups()

        if not groups:
            self._send(chat_id, "No enabled groups.")
            return

        text = " ".join(args)
        success = 0
        failed = 0

        for group in groups:
            group_id = group.get("group_id")

            if not group_id:
                failed += 1
                continue

            try:
                self.telegram.send_message(
                    chat_id=str(group_id),
                    text=text,
                    parse_mode="HTML",
                )
                success += 1
            except Exception as exc:
                logger.error("Broadcast failed %s: %s", group_id, exc)
                failed += 1

        self._send(
            chat_id,
            f"📢 <b>Broadcast Complete</b>\n"
            f"✅ Sent: {success}\n"
            f"❌ Failed: {failed}\n"
            f"Total: {len(groups)}",
        )

    def cmd_post(self, chat_id: Any, args: List[str]) -> None:
        if not args:
            self._send(chat_id, "Usage: /post message")
            return

        if not self.telegram:
            self._send(chat_id, "❌ Telegram unavailable.")
            return

        try:
            result = self.telegram.send_message(
                chat_id=self.config.telegram_channel_id,
                text=" ".join(args),
                parse_mode="HTML",
            )

            self._send(
                chat_id,
                "✅ Posted" if result else "❌ Failed",
            )

        except Exception as exc:
            self._send(chat_id, f"❌ {exc}")

    def cmd_share(self, chat_id: Any, args: List[str]) -> None:
        """Share channel post to approved groups."""
        if not args:
            self._send(chat_id, "Usage: /share [message_id]")
            return

        if not self.telegram or not self.groups:
            self._send(chat_id, "❌ Not available")
            return

        try:
            message_id = int(args[0])
        except ValueError:
            self._send(chat_id, "❌ Invalid message_id")
            return

        groups = self.groups.get_approved_groups()

        if not groups:
            self._send(chat_id, "No approved groups.")
            return

        success = 0
        failed = 0

        for group in groups:
            group_id = group.get("group_id")

            if not group_id:
                failed += 1
                continue

            try:
                self.telegram.forward_message(
                    from_chat_id=self.config.telegram_channel_id,
                    message_id=message_id,
                    to_chat_id=str(group_id),
                )
                success += 1
            except Exception as exc:
                logger.error("Share failed %s: %s", group_id, exc)
                failed += 1

        self._send(
            chat_id,
            f"📤 <b>Share Complete</b>\n"
            f"✅ Shared: {success}\n"
            f"❌ Failed: {failed}",
        )

    def cmd_editpost(self, chat_id: Any, args: List[str]) -> None:
        """Edit channel post."""
        if len(args) < 2:
            self._send(chat_id, "Usage: /editpost [message_id] [new text]")
            return

        if not self.telegram:
            self._send(chat_id, "❌ Not available")
            return

        try:
            message_id = int(args[0])
            new_text = " ".join(args[1:])

            result = self.telegram._make_request(
                "POST",
                "editMessageText",
                {
                    "chat_id": self.config.telegram_channel_id,
                    "message_id": message_id,
                    "text": new_text,
                    "parse_mode": "HTML",
                },
            )
            self._send(chat_id, "✅ Edited" if result else "❌ Failed")
        except Exception as exc:
            self._send(chat_id, f"❌ {exc}")

    def cmd_deletepost(self, chat_id: Any, args: List[str]) -> None:
        """Delete channel post."""
        if not args:
            self._send(chat_id, "Usage: /deletepost [message_id]")
            return

        if not self.telegram:
            self._send(chat_id, "❌ Not available")
            return

        try:
            result = self.telegram._make_request(
                "POST",
                "deleteMessage",
                {
                    "chat_id": self.config.telegram_channel_id,
                    "message_id": int(args[0]),
                },
            )
            self._send(chat_id, "✅ Deleted" if result else "❌ Failed")
        except Exception as exc:
            self._send(chat_id, f"❌ {exc}")

    # ========================================================
    # LINK SCANNER
    # ========================================================

    def _extract_links(self, text: str) -> List[str]:
        if not text:
            return []

        links = set()

        for pattern in self.LINK_PATTERNS:
            links.update(re.findall(pattern, text, re.IGNORECASE))

        return list(links)

    def scan_message_for_links(self, message: Dict[str, Any]) -> None:
        if not self.database:
            return

        text = message.get("text", "")
        source = str(message.get("chat", {}).get("id", ""))

        for link in self._extract_links(text):
            try:
                self.database.execute(
                    """
                    INSERT OR IGNORE INTO found_links
                    (link, source_group_id)
                    VALUES (?, ?)
                    """,
                    (link, source),
                )
                logger.info("Link found: @%s", link)
            except Exception as exc:
                logger.error("Link save failed: %s", exc)

    def cmd_scan(self, chat_id: Any) -> None:
        if not self.database:
            self._send(chat_id, "❌ Database unavailable.")
            return

        try:
            links = self.database.query(
                """
                SELECT * FROM found_links
                WHERE status='found'
                ORDER BY last_seen DESC
                """
            )
        except Exception:
            links = []

        if not links:
            self._send(chat_id, "🔍 No links found.")
            return

        lines = ["<b>🔗 Found Links</b>"]

        for i, item in enumerate(links, 1):
            lines.append(f"{i}. @{item.get('link', '?')}")

        lines.extend([
            "",
            "/join @group",
            "/joinall",
            "/reject @group",
            "/clearlinks",
        ])

        self._send(chat_id, "\n".join(lines))

    def cmd_join(self, chat_id: Any, args: List[str]) -> None:
        if not args:
            self._send(chat_id, "Usage: /join @group")
            return

        if not self.telegram:
            self._send(chat_id, "❌ Telegram unavailable.")
            return

        link = args[0].replace("@", "").strip()

        try:
            result = self.telegram.get_chat(f"@{link}")

            if result:
                if self.database:
                    self.database.execute(
                        "UPDATE found_links SET status='approved' WHERE link=?",
                        (link,),
                    )

                self._send(
                    chat_id,
                    f"✅ Found: @{link}\n"
                    f"⚠️ Bot API နဲ့ auto-join မလုပ်နိုင်ပါ။",
                )
            else:
                self._send(chat_id, "❌ Not found.")

        except Exception as exc:
            self._send(chat_id, f"❌ {exc}")

    def cmd_joinall(self, chat_id: Any) -> None:
        if not self.database:
            self._send(chat_id, "❌ Database unavailable.")
            return

        try:
            links = self.database.query(
                "SELECT link FROM found_links WHERE status='found'"
            )
        except Exception:
            links = []

        if not links:
            self._send(chat_id, "No links.")
            return

        self._send(
            chat_id,
            f"🔎 Found {len(links)} links.\n"
            f"⚠️ Bot API auto-join မရပါ။",
        )

        for item in links:
            self.cmd_join(chat_id, [item.get("link", "")])

    def cmd_reject(self, chat_id: Any, args: List[str]) -> None:
        if not args:
            self._send(chat_id, "Usage: /reject @group")
            return

        if not self.database:
            return

        try:
            self.database.execute(
                "UPDATE found_links SET status='rejected' WHERE link=?",
                (args[0].replace("@", ""),),
            )
            self._send(chat_id, "✅ Rejected.")
        except Exception as exc:
            self._send(chat_id, f"❌ {exc}")

    def cmd_clearlinks(self, chat_id: Any) -> None:
        if not self.database:
            return

        try:
            self.database.execute(
                "DELETE FROM found_links WHERE status='found'"
            )
            self._send(chat_id, "✅ Links cleared.")
        except Exception as exc:
            self._send(chat_id, f"❌ {exc}")

    # ========================================================
    # MODERATION
    # ========================================================

    def cmd_mod(self, chat_id: Any, args: List[str], action: str) -> None:
        if len(args) < 2:
            self._send(chat_id, f"Usage: /{action} group_id user_id")
            return

        if not self.telegram:
            self._send(chat_id, "❌ Telegram unavailable.")
            return

        try:
            result = self.telegram._make_request(
                "POST",
                action,
                {
                    "chat_id": args[0],
                    "user_id": args[1].replace("@", ""),
                },
            )

            self._send(chat_id, f"✅ {action}" if result else "❌ Failed")

        except Exception as exc:
            self._send(chat_id, f"❌ {exc}")

    def cmd_kick(self, chat_id: Any, args: List[str]) -> None:
        if len(args) < 2:
            self._send(chat_id, "Usage: /kick group_id user_id")
            return

        self.cmd_mod(chat_id, args, "banChatMember")
        self.cmd_mod(chat_id, args, "unbanChatMember")

    def cmd_pin(self, chat_id: Any, args: List[str]) -> None:
        if not args:
            self._send(chat_id, "Usage: /pin message_id")
            return

        if not self.telegram:
            return

        try:
            result = self.telegram._make_request(
                "POST",
                "pinChatMessage",
                {
                    "chat_id": self.config.telegram_channel_id,
                    "message_id": int(args[0]),
                },
            )

            self._send(chat_id, "✅ Pinned" if result else "❌ Failed")

        except Exception as exc:
            self._send(chat_id, f"❌ {exc}")

    def cmd_unpin(self, chat_id: Any) -> None:
        if not self.telegram:
            return

        try:
            result = self.telegram._make_request(
                "POST",
                "unpinChatMessage",
                {"chat_id": self.config.telegram_channel_id},
            )

            self._send(chat_id, "✅ Unpinned" if result else "❌ Failed")

        except Exception as exc:
            self._send(chat_id, f"❌ {exc}")

    # ========================================================
    # SCHEDULE
    # ========================================================

    def cmd_settime(self, chat_id: Any, args: List[str]) -> None:
        if len(args) < 2:
            self._send(chat_id, "Usage: /settime morning/evening HH:MM")
            return

        period = args[0].lower()
        time_str = args[1]

        if period not in ("morning", "evening"):
            self._send(chat_id, "❌ Invalid period.")
            return

        if not re.fullmatch(r"([01]?[0-9]|2[0-3]):[0-5][0-9]", time_str):
            self._send(chat_id, "❌ Invalid time.")
            return

        self._set_state(f"{period}_time", time_str)
        self._send(chat_id, f"✅ {period.capitalize()}: {time_str}")

    def cmd_setmonth(self, chat_id: Any, args: List[str]) -> None:
        if not args:
            self._send(chat_id, "Usage: /setmonth month_id")
            return

        if not self._set_state("current_month", args[0]):
            self._send(chat_id, "❌ Failed to set month.")
            return

        self._send(chat_id, f"✅ Month: {args[0]}")

    def cmd_scheduled(self, chat_id: Any) -> None:
        month = self._get_state("current_month", "python_month_1")
        morning = self._get_state("morning_time", "08:00")
        evening = self._get_state("evening_time", "20:00")

        self._send(
            chat_id,
            f"📋 <b>Schedule</b>\n"
            f"Month: {month}\n"
            f"Morning: {morning}\n"
            f"Evening: {evening}\n"
            f"Timezone: {self.config.timezone}",
        )

    def cmd_skipday(self, chat_id: Any) -> None:
        if not self.database:
            self._send(chat_id, "❌ Database unavailable.")
            return

        try:
            row = self.database.query_one(
                "SELECT MAX(day_number) AS day FROM lessons WHERE status='published'"
            )

            current = int((row or {}).get("day", 0) or 0)
            next_day = current + 1

            self._set_state("skip_to_day", str(next_day))
            self._send(chat_id, f"✅ Skipped to Day {next_day}")

        except Exception as exc:
            self._send(chat_id, f"❌ {exc}")

    def cmd_resetday(self, chat_id: Any, args: List[str]) -> None:
        if not args:
            self._send(chat_id, "Usage: /resetday day_number")
            return

        try:
            day = int(args[0])

            if day < 1:
                raise ValueError

            self._set_state("reset_to_day", str(day))
            self._send(chat_id, f"✅ Reset to Day {day}")

        except ValueError:
            self._send(chat_id, "❌ Invalid day number.")

    # ========================================================
    # STATS / MAINTENANCE
    # ========================================================

    def cmd_stats(self, chat_id: Any) -> None:
        if not self.database:
            self._send(chat_id, "❌ Database unavailable.")
            return

        try:
            lessons = self.database.query_one(
                "SELECT COUNT(*) AS count FROM lessons WHERE status='published'"
            )
            groups = self.database.query_one(
                "SELECT COUNT(*) AS count FROM groups WHERE status='approved'"
            )
            links = self.database.query_one(
                "SELECT COUNT(*) AS count FROM found_links WHERE status='found'"
            )
            shares = self.database.query_one(
                "SELECT COALESCE(SUM(total_shares), 0) AS total FROM groups"
            )

            self._send(
                chat_id,
                f"📊 <b>Statistics</b>\n"
                f"Published Lessons: {int((lessons or {}).get('count', 0) or 0)}\n"
                f"Approved Groups: {int((groups or {}).get('count', 0) or 0)}\n"
                f"Pending Links: {int((links or {}).get('count', 0) or 0)}\n"
                f"Total Shares: {int((shares or {}).get('total', 0) or 0)}",
            )

        except Exception as exc:
            self._send(chat_id, f"❌ {exc}")

    def cmd_lessonstatus(self, chat_id: Any) -> None:
        if not self.database:
            self._send(chat_id, "❌ Database unavailable.")
            return

        month = self._get_state("current_month", "python_month_1")

        try:
            row = self.database.query_one(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN status='published' THEN 1 ELSE 0 END) AS published,
                    SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS failed,
                    SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) AS pending
                FROM lessons
                WHERE month=?
                """,
                (month,),
            )

            total = int((row or {}).get("total", 0) or 0)
            published = int((row or {}).get("published", 0) or 0)
            failed = int((row or {}).get("failed", 0) or 0)
            pending = int((row or {}).get("pending", 0) or 0)

            self._send(
                chat_id,
                f"📚 <b>Lesson Status</b>\n"
                f"Month: {month}\n"
                f"Total: {total}\n"
                f"✅ Published: {published}\n"
                f"❌ Failed: {failed}\n"
                f"⏳ Pending: {pending}",
            )

        except Exception as exc:
            self._send(chat_id, f"❌ {exc}")

    def cmd_agentstatus(self, chat_id: Any) -> None:
        """Show AI Teacher Agent status."""
        month = self._get_state("current_month", "python_month_1")
        paused = self._get_state("paused", "0") == "1"
        state = "⏸️ PAUSED" if paused else "▶️ ACTIVE"

        try:
            lessons = self.database.query_one(
                "SELECT COUNT(*) AS c FROM lessons WHERE month=? AND status='published'",
                (month,),
            )
            published = int((lessons or {}).get("c", 0) or 0)

            self._send(
                chat_id,
                f"🤖 <b>Agent Status</b>\n"
                f"State: {state}\n"
                f"Month: {month}\n"
                f"Published: {published} lessons",
            )
        except Exception as exc:
            self._send(chat_id, f"❌ {exc}")

    def cmd_uptime(self, chat_id: Any) -> None:
        """Show bot uptime."""
        start_time = float(self._get_state("start_time", str(time.time())))
        uptime_seconds = int(time.time() - start_time)

        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        minutes = (uptime_seconds % 3600) // 60

        uptime_str = ""
        if days > 0:
            uptime_str += f"{days}d "
        if hours > 0:
            uptime_str += f"{hours}h "
        uptime_str += f"{minutes}m"

        self._send(chat_id, f"⏱️ <b>Uptime</b>\nRunning: {uptime_str}")

    def cmd_backup(self, chat_id: Any) -> None:
        try:
            src = Path(self.config.sqlite_db_path)
            dst = src.with_suffix(".backup.db")
            shutil.copy2(src, dst)
            self._send(chat_id, f"✅ Backup created:\n{dst}")
        except Exception as exc:
            self._send(chat_id, f"❌ {exc}")

    def cmd_clearlogs(self, chat_id: Any) -> None:
        if not self.database:
            return

        try:
            self.database.execute(
                "DELETE FROM admin_logs WHERE executed_at < datetime('now', '-7 days')"
            )
            self._send(chat_id, "✅ Old logs cleared.")
        except Exception as exc:
            self._send(chat_id, f"❌ {exc}")

    def cmd_restart(self, chat_id: Any) -> None:
        """Restart the bot."""
        self._send(chat_id, "🔄 Restarting...")

        try:
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as exc:
            self._send(chat_id, f"❌ Restart failed: {exc}")

    # ========================================================
    # AI & PROPOSALS
    # ========================================================

    def cmd_proposals(self, chat_id: Any) -> None:
        """Show pending AI proposals."""
        if not self.database:
            self._send(chat_id, "❌ Database unavailable.")
            return

        try:
            proposals = self.database.query(
                "SELECT * FROM proposals WHERE status='pending' ORDER BY created_at DESC"
            )
        except Exception:
            proposals = []

        if not proposals:
            self._send(chat_id, "No pending proposals.")
            return

        lines = ["<b>📝 Pending Proposals:</b>"]

        for p in proposals:
            lines.append(
                f"#{p.get('id', '?')} [{p.get('proposal_type', '?')}] "
                f"{p.get('title', '?')}"
            )

        self._send(chat_id, "\n".join(lines))

    def cmd_feedback(self, chat_id: Any) -> None:
        """Show student feedback."""
        if not self.database:
            self._send(chat_id, "❌ Database unavailable.")
            return

        try:
            feedback = self.database.query(
                "SELECT * FROM student_feedback ORDER BY created_at DESC LIMIT 20"
            )
        except Exception:
            feedback = []

        if not feedback:
            self._send(chat_id, "No feedback yet.")
            return

        lines = ["<b>💬 Student Feedback:</b>"]

        for f in feedback:
            rating = f.get("rating", 0)
            content = f.get("content", "")
            lines.append(f"⭐ {rating}/5 — {content}")

        self._send(chat_id, "\n".join(lines))
    # ========================================================
    # HELP
    # ========================================================

    def cmd_help(self, chat_id: Any) -> None:
        text = (
            "<b>📋 Owner Commands</b>\n\n"

            "<b>Basic</b>\n"
            "/status - Bot status\n"
            "/pause - Pause publishing\n"
            "/resume - Resume publishing\n\n"

            "<b>Groups</b>\n"
            "/groups - Approved groups\n"
            "/grouplist - All groups by status\n"
            "/approve @group - Approve\n"
            "/remove @group - Remove\n\n"

            "<b>Posting</b>\n"
            "/global message - Broadcast to approved\n"
            "/broadcast message - Broadcast to all enabled\n"
            "/post message - Post to channel\n"
            "/forcepost message - Force post\n"
            "/share message_id - Share post to groups\n"
            "/editpost message_id text - Edit post\n"
            "/deletepost message_id - Delete post\n\n"

            "<b>Links</b>\n"
            "/scan - Show found links\n"
            "/links - Alias for scan\n"
            "/join @group - Join group\n"
            "/joinall - Join all\n"
            "/reject @group - Reject link\n"
            "/clearlinks - Clear links\n\n"

            "<b>Moderation</b>\n"
            "/ban group_id user_id\n"
            "/unban group_id user_id\n"
            "/kick group_id user_id\n"
            "/pin message_id\n"
            "/unpin\n\n"

            "<b>Schedule</b>\n"
            "/settime morning 09:00\n"
            "/setmonth month_id\n"
            "/scheduled\n"
            "/skipday\n"
            "/resetday day\n\n"

            "<b>Stats</b>\n"
            "/stats\n"
            "/lessonstatus\n"
            "/agentstatus\n"
            "/uptime\n\n"

            "<b>Maintenance</b>\n"
            "/backup\n"
            "/clearlogs\n"
            "/restart\n\n"

            "<b>AI</b>\n"
            "/proposals\n"
            "/feedback\n\n"

            "/help - This help"
        )

        self._send(chat_id, text)


# ============================================================
# FACTORY
# ============================================================

def create_owner_handler(
    config: Optional[Config] = None,
    database: Optional[DatabaseInterface] = None,
    telegram: Optional[TelegramClient] = None,
    group_manager: Optional[GroupManager] = None,
) -> OwnerHandler:
    """Factory function for OwnerHandler."""
    return OwnerHandler(
        config=config,
        database=database,
        telegram=telegram,
        group_manager=group_manager,
    )
