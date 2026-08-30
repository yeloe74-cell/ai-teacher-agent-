# modules/teacher_agent.py
"""
Teacher Agent for AI Teacher Bot.

Part 6 - Autonomous Teacher Agent & Approval System

The Agent CAN:
- Analyze current month progress
- Plan next month curriculum
- Generate proposals for Owner approval
- Learn from student feedback
- Log its activities

The Agent CANNOT:
- Change curriculum directly
- Modify config directly
- Publish posts without approval
- Approve its own proposals

Authority always remains with the Owner.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from config import Config, get_config
from database import DatabaseInterface
from modules.ai_generator import AIGenerator, create_ai_generator

logger = logging.getLogger(__name__)


class TeacherAgent:
    """
    Autonomous Teacher Agent.

    Thinks freely. Asks permission before acting.
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        database: Optional[DatabaseInterface] = None,
        ai_generator: Optional[AIGenerator] = None,
    ):
        self.config = config or get_config()
        self.database = database
        self.ai = ai_generator or create_ai_generator(self.config)

        logger.info("TeacherAgent initialized")

    # ========================================================
    # LOGGING
    # ========================================================

    def _log_activity(self, activity_type: str, description: str) -> None:
        """Log agent activity to database."""
        if not self.database:
            return

        try:
            self.database.execute(
                """
                INSERT INTO agent_logs (activity_type, description)
                VALUES (?, ?)
                """,
                (activity_type, description),
            )
        except Exception as exc:
            logger.error(f"Agent log failed: {exc}")

    # ========================================================
    # PROPOSALS
    # ========================================================

    def create_proposal(
        self,
        proposal_type: str,
        title: str,
        content: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Create a proposal for Owner review.

        The Agent NEVER applies changes directly.
        It only creates proposals.
        """
        if not self.database:
            return None

        try:
            self.database.execute(
                """
                INSERT INTO proposals
                (proposal_type, title, content, status, created_by)
                VALUES (?, ?, ?, 'pending', 'agent')
                """,
                (proposal_type, title, content),
            )

            result = self.database.query_one(
                "SELECT * FROM proposals ORDER BY id DESC LIMIT 1"
            )

            self._log_activity(
                "proposal_created",
                f"Created proposal: {title}",
            )

            logger.info(f"Proposal created: {title}")
            return result

        except Exception as exc:
            logger.error(f"Failed to create proposal: {exc}")
            return None

    def get_pending_proposals(self) -> List[Dict[str, Any]]:
        """Get all pending proposals."""
        if not self.database:
            return []

        try:
            return self.database.query("""
                SELECT * FROM proposals
                WHERE status = 'pending'
                ORDER BY created_at DESC
                """)
        except Exception as exc:
            logger.error(f"Failed to get proposals: {exc}")
            return []

    def get_all_proposals(self) -> List[Dict[str, Any]]:
        """Get all proposals."""
        if not self.database:
            return []

        try:
            return self.database.query(
                "SELECT * FROM proposals ORDER BY created_at DESC"
            )
        except Exception as exc:
            logger.error(f"Failed to get proposals: {exc}")
            return []

    def approve_proposal(
        self,
        proposal_id: int,
        reviewer: str,
        notes: str = "",
    ) -> bool:
        """Approve a proposal (Owner only)."""
        if not self.database:
            return False

        try:
            self.database.execute(
                """
                UPDATE proposals
                SET status='approved',
                    reviewed_by=?,
                    reviewed_at=CURRENT_TIMESTAMP,
                    review_notes=?
                WHERE id=?
                """,
                (reviewer, notes, proposal_id),
            )

            self._log_activity(
                "proposal_approved",
                f"Proposal #{proposal_id} approved by {reviewer}",
            )

            return True
        except Exception as exc:
            logger.error(f"Failed to approve proposal: {exc}")
            return False

    def reject_proposal(
        self,
        proposal_id: int,
        reviewer: str,
        notes: str = "",
    ) -> bool:
        """Reject a proposal (Owner only)."""
        if not self.database:
            return False

        try:
            self.database.execute(
                """
                UPDATE proposals
                SET status='rejected',
                    reviewed_by=?,
                    reviewed_at=CURRENT_TIMESTAMP,
                    review_notes=?
                WHERE id=?
                """,
                (reviewer, notes, proposal_id),
            )

            self._log_activity(
                "proposal_rejected",
                f"Proposal #{proposal_id} rejected by {reviewer}",
            )

            return True
        except Exception as exc:
            logger.error(f"Failed to reject proposal: {exc}")
            return False

    # ========================================================
    # MONTH ANALYSIS
    # ========================================================

    def analyze_current_month(self, month: str) -> Dict[str, Any]:
        """
        Analyze current month progress.
        Returns summary data for AI analysis.
        """
        if not self.database:
            return {}

        try:
            lessons = self.database.query_one(
                """
                SELECT 
                    COUNT(*) AS total,
                    SUM(CASE WHEN status='published' THEN 1 ELSE 0 END) AS published,
                    SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS failed,
                    SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) AS pending
                FROM lessons
                WHERE month = ?
                """,
                (month,),
            )

            groups = self.database.query_one(
                "SELECT COUNT(*) AS count FROM groups WHERE status='approved'"
            )

            shares = self.database.query_one(
                "SELECT COALESCE(SUM(total_shares), 0) AS total FROM groups"
            )

            feedback = self.database.query_one(
                "SELECT COUNT(*) AS count FROM student_feedback"
            )

            return {
                "month": month,
                "total_lessons": int((lessons or {}).get("total", 0) or 0),
                "published": int((lessons or {}).get("published", 0) or 0),
                "failed": int((lessons or {}).get("failed", 0) or 0),
                "pending": int((lessons or {}).get("pending", 0) or 0),
                "approved_groups": int((groups or {}).get("count", 0) or 0),
                "total_shares": int((shares or {}).get("total", 0) or 0),
                "feedback_count": int((feedback or {}).get("count", 0) or 0),
            }

        except Exception as exc:
            logger.error(f"Failed to analyze month: {exc}")
            return {}

    # ========================================================
    # NEXT MONTH PLANNING
    # ========================================================

    def plan_next_month(self, current_month: str) -> Optional[Dict[str, Any]]:
        """
        Analyze current month and create a proposal for next month.
        Uses AI to generate recommendations.
        """
        analysis = self.analyze_current_month(current_month)

        if not analysis:
            return None

        # Build prompt for AI
        prompt = self._build_planning_prompt(analysis)

        try:
            # Generate AI recommendation
            recommendation = self.ai.generate_custom_content(
                prompt=prompt,
                max_tokens=500,
            )

            # Create proposal
            proposal = self.create_proposal(
                proposal_type="curriculum_plan",
                title=f"Next Month Plan (after {current_month})",
                content=recommendation,
            )

            return proposal

        except Exception as exc:
            logger.error(f"Failed to plan next month: {exc}")
            return None

    def _build_planning_prompt(self, analysis: Dict[str, Any]) -> str:
        """Build AI prompt for next month planning."""
        return f"""
မင်းက AI Teacher Bot ရဲ့ Teacher Agent တစ်ယောက်ပါ။
လက်ရှိ month ရဲ့ ရလဒ်တွေကို အခြေခံပြီး နောက်လ curriculum အတွက် အကြံပြုချက်တွေ ပေးပါ။

လက်ရှိ အခြေအနေ:
- Month: {analysis.get('month', 'unknown')}
- Total Lessons: {analysis.get('total_lessons', 0)}
- Published: {analysis.get('published', 0)}
- Failed: {analysis.get('failed', 0)}
- Pending: {analysis.get('pending', 0)}
- Approved Groups: {analysis.get('approved_groups', 0)}
- Total Shares: {analysis.get('total_shares', 0)}
- Student Feedback Count: {analysis.get('feedback_count', 0)}

အကြံပြုချက် ပေးရမယ့် အချက်တွေ:
1. နောက်လ ဘာ topic တွေ ထပ်ထည့်သင့်လဲ
2. ဘယ် topic တွေကို ပိုအသေးစိတ် သင်သင့်လဲ
3. Student engagement တိုးအောင် ဘာလုပ်သင့်လဲ
4. Failed lessons တွေ ပြန်ပြင်ဖို့ ဘာလုပ်သင့်လဲ

မြန်မာလို ရှင်းရှင်းလင်းလင်း ရေးပေးပါ။
"""

    # ========================================================
    # FEEDBACK ANALYSIS
    # ========================================================

    def analyze_feedback(self) -> Optional[Dict[str, Any]]:
        """Analyze student feedback and create improvement proposal."""
        if not self.database:
            return None

        try:
            feedback = self.database.query("""
                SELECT * FROM student_feedback
                ORDER BY created_at DESC
                LIMIT 50
                """)
        except Exception as exc:
            logger.error(f"Failed to get feedback: {exc}")
            return None

        if not feedback:
            return None

        # Build prompt
        feedback_text = "\n".join(
            [
                f"- [{f.get('feedback_type', 'general')}] {f.get('content', '')} "
                f"(rating: {f.get('rating', 0)}/5)"
                for f in feedback
            ]
        )

        prompt = f"""
မင်းက AI Teacher Bot ရဲ့ Teacher Agent ပါ။
Student တွေရဲ့ feedback တွေကို ခွဲခြမ်းစိတ်ဖြာပြီး သင်ကြားရေး တိုးတက်အောင် အကြံပြုချက် ပေးပါ။

Feedback တွေ:
{feedback_text}

အကြံပြုချက် ပေးရမယ့် အချက်တွေ:
1. ဘယ် topic တွေ ခက်ခဲနေလဲ
2. ဘာတွေ ထပ်ထည့်သင့်လဲ
3. သင်ကြားနည်း ဘယ်လို ပြောင်းသင့်လဲ

မြန်မာလို ရှင်းရှင်းလင်းလင်း ရေးပါ။
"""

        try:
            recommendation = self.ai.generate_custom_content(
                prompt=prompt,
                max_tokens=400,
            )

            proposal = self.create_proposal(
                proposal_type="feedback_analysis",
                title="Student Feedback Analysis",
                content=recommendation,
            )

            return proposal

        except Exception as exc:
            logger.error(f"Failed to analyze feedback: {exc}")
            return None

    # ========================================================
    # FEEDBACK COLLECTION
    # ========================================================

    def collect_feedback(
        self,
        user_id: str,
        feedback_type: str,
        content: str,
        rating: int = 0,
    ) -> bool:
        """Collect student feedback."""
        if not self.database:
            return False

        try:
            self.database.execute(
                """
                INSERT INTO student_feedback
                (user_id, feedback_type, content, rating)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, feedback_type, content, rating),
            )

            self._log_activity(
                "feedback_collected",
                f"Feedback from {user_id}",
            )

            return True
        except Exception as exc:
            logger.error(f"Failed to collect feedback: {exc}")
            return False

    # ========================================================
    # AGENT STATUS
    # ========================================================

    def get_agent_status(self) -> Dict[str, Any]:
        """Get agent status summary."""
        if not self.database:
            return {}

        try:
            proposals = self.database.query_one(
                "SELECT COUNT(*) AS count FROM proposals WHERE status='pending'"
            )
            logs = self.database.query_one("SELECT COUNT(*) AS count FROM agent_logs")
            feedback = self.database.query_one(
                "SELECT COUNT(*) AS count FROM student_feedback"
            )

            return {
                "pending_proposals": int((proposals or {}).get("count", 0) or 0),
                "total_logs": int((logs or {}).get("count", 0) or 0),
                "total_feedback": int((feedback or {}).get("count", 0) or 0),
            }

        except Exception as exc:
            logger.error(f"Failed to get agent status: {exc}")
            return {}

    # ========================================================
    # AGENT LOGS
    # ========================================================

    def get_recent_logs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent agent activity logs."""
        if not self.database:
            return []

        try:
            return self.database.query(
                """
                SELECT * FROM agent_logs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            )
        except Exception as exc:
            logger.error(f"Failed to get logs: {exc}")
            return []


# ============================================================
# FACTORY
# ============================================================


def create_teacher_agent(
    config: Optional[Config] = None,
    database: Optional[DatabaseInterface] = None,
    ai_generator: Optional[AIGenerator] = None,
) -> TeacherAgent:
    """Factory function for TeacherAgent."""
    return TeacherAgent(
        config=config,
        database=database,
        ai_generator=ai_generator,
    )
