# modules/owner_extra.py
"""
Extra Owner Commands for AI Teacher Bot.

To add new command:
1. Add method: def cmd_xxx(self, chat_id, args): ...
2. Register in dispatch() method below.
Done.
"""

import logging
from typing import Any, Dict, List, Optional

from config import Config, get_config
from database import DatabaseInterface
from modules.group_manager import GroupManager
from modules.telegram_client import TelegramClient
from modules.teacher_agent import TeacherAgent
from modules.student_system import StudentSystem

logger = logging.getLogger(__name__)


class OwnerExtra:
    """Extra Owner commands — အသစ်ထည့်ချင်ရင် ဒီထဲပဲ ထည့်မယ်။"""

    def __init__(
        self,
        config: Optional[Config] = None,
        database: Optional[DatabaseInterface] = None,
        telegram: Optional[TelegramClient] = None,
        groups: Optional[GroupManager] = None,
        agent: Optional[TeacherAgent] = None,
        student_system: Optional[StudentSystem] = None,
    ):
        self.config = config or get_config()
        self.database = database
        self.telegram = telegram
        self.groups = groups
        self.agent = agent
        self.student_system = student_system

        logger.debug("OwnerExtra initialized")

    # ========================================================
    # HELPERS
    # ========================================================

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
    # DISPATCH
    # ========================================================

    def dispatch(
        self,
        command: str,
        args: List[str],
        chat_id: Any,
        owner_id: str,
    ) -> bool:
        """
        Dispatch extra commands.

        Returns:
            True if command was handled.
            False if command is not an extra command.
        """
        handlers = {
            # Part 7: Student Project
            "/createchallenge": lambda: self.cmd_createchallenge(chat_id, args),
            "/submissions": lambda: self.cmd_submissions(chat_id, args),
            "/review": lambda: self.cmd_review(chat_id, args, owner_id),
            "/projectstats": lambda: self.cmd_projectstats(chat_id),
        }

        handler = handlers.get(command)

        if not handler:
            return False

        try:
            handler()
        except Exception as exc:
            logger.exception("Extra command failed: %s", command)
            self._send(chat_id, f"❌ Error: {exc}")

        return True

    # ========================================================
    # STUDENT PROJECT COMMANDS (Part 7)
    # ========================================================

    def cmd_createchallenge(self, chat_id: Any, args: List[str]) -> None:
        """
        Create project challenge.
        Usage: /createchallenge [title] | [description] | [requirements]
        """
        if len(args) < 3:
            self._send(
                chat_id,
                "Usage: /createchallenge [title] | [description] | [requirements]",
            )
            return

        full_text = " ".join(args)
        parts = full_text.split("|")

        if len(parts) < 3:
            self._send(chat_id, "Need: title | description | requirements")
            return

        month = self._get_state("current_month", "python_month_1")
        title = parts[0].strip()
        description = parts[1].strip()
        requirements = parts[2].strip()

        if not self.student_system:
            self._send(chat_id, "❌ Student system not available")
            return

        challenge = self.student_system.create_challenge(
            month=month,
            title=title,
            description=description,
            requirements=requirements,
        )

        if challenge:
            self._send(chat_id, f"✅ Challenge created: {title}")
        else:
            self._send(chat_id, "❌ Failed to create challenge")

    def cmd_submissions(self, chat_id: Any, args: List[str]) -> None:
        """
        Show submissions.
        Usage: /submissions [pending/passed/failed]
        """
        if not self.student_system:
            self._send(chat_id, "❌ Student system not available")
            return

        status = args[0] if args else None
        submissions = self.student_system.get_submissions(status=status)

        if not submissions:
            self._send(chat_id, "No submissions.")
            return

        lines = ["<b>📝 Submissions:</b>"]

        for s in submissions[:20]:
            sub_id = s.get("id", "?")
            user = s.get("user_id", "?")
            repo = s.get("project_repo", "N/A")
            status_val = s.get("review_status", "?")
            lines.append(f"#{sub_id} | {user} | {status_val} | {repo}")

        self._send(chat_id, "\n".join(lines))

    def cmd_review(
        self,
        chat_id: Any,
        args: List[str],
        owner_id: str,
    ) -> None:
        """
        Review a submission.
        Usage: /review [id] [passed/failed] [feedback]
        """
        if len(args) < 2:
            self._send(chat_id, "Usage: /review [id] [passed/failed] [feedback]")
            return

        if not self.student_system:
            self._send(chat_id, "❌ Student system not available")
            return

        try:
            submission_id = int(args[0])
            status = args[1].lower()
            feedback = " ".join(args[2:]) if len(args) > 2 else ""

            if status not in ("passed", "failed"):
                self._send(chat_id, "❌ Status must be passed or failed")
                return

            if self.student_system.review_submission(
                submission_id=submission_id,
                reviewer=owner_id,
                status=status,
                feedback=feedback,
            ):
                self._send(chat_id, f"✅ Submission #{submission_id} → {status}")
            else:
                self._send(chat_id, "❌ Failed to review")

        except ValueError:
            self._send(chat_id, "❌ Invalid ID")

    def cmd_projectstats(self, chat_id: Any) -> None:
        """Show project submission stats."""
        if not self.student_system:
            self._send(chat_id, "❌ Student system not available")
            return

        month = self._get_state("current_month", "python_month_1")
        stats = self.student_system.get_submission_stats(month)

        self._send(
            chat_id,
            f"📊 <b>Project Stats</b>\n"
            f"Month: {month}\n"
            f"Total: {stats.get('total', 0)}\n"
            f"✅ Passed: {stats.get('passed', 0)}\n"
            f"❌ Failed: {stats.get('failed', 0)}\n"
            f"⏳ Pending: {stats.get('pending', 0)}",
        )
     def cmd_emergency(self, chat_id: Any) -> None:
        """Toggle emergency stop."""
        if not self.safety:
            self._send(chat_id, "❌ Safety manager not available")
            return

        current = self.safety.is_emergency_stopped()

        if current:
            self.safety.set_emergency_stop(False)
            self._send(chat_id, "✅ Emergency stop DEACTIVATED")
        else:
            self.safety.set_emergency_stop(True)
            self._send(chat_id, "🛑 Emergency stop ACTIVATED")
            
# ============================================================
# FACTORY
# ============================================================


def create_owner_extra(
    config: Optional[Config] = None,
    database: Optional[DatabaseInterface] = None,
    telegram: Optional[TelegramClient] = None,
    groups: Optional[GroupManager] = None,
    agent: Optional[TeacherAgent] = None,
    student_system: Optional[StudentSystem] = None,
) -> OwnerExtra:
    """Factory function for OwnerExtra."""
    return OwnerExtra(
        config=config,
        database=database,
        telegram=telegram,
        groups=groups,
        agent=agent,
        student_system=student_system,
    )
    
