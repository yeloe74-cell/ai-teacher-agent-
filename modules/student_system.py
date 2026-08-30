# modules/student_system.py
"""
Student Project System for AI Teacher Bot.

Part 7 - Student Project System

Handles:
- Project challenge creation
- Student submissions
- Review workflow
- Feedback management
"""

import logging
from typing import Any, Dict, List, Optional

from config import Config, get_config
from database import DatabaseInterface

logger = logging.getLogger(__name__)


class StudentSystemError(Exception):
    """Base exception for student system."""
    pass


class StudentSystem:
    """Handles student project challenges and submissions."""

    def __init__(
        self,
        config: Optional[Config] = None,
        database: Optional[DatabaseInterface] = None,
    ):
        self.config = config or get_config()
        self.database = database

        logger.debug("StudentSystem initialized")

    # ========================================================
    # PROJECT CHALLENGES
    # ========================================================

    def create_challenge(
        self,
        month: str,
        title: str,
        description: str,
        requirements: str,
        deadline: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Create a project challenge.
        
        Challenge contains requirements only.
        No solution code is provided.
        """
        if not self.database:
            return None

        try:
            self.database.execute(
                """
                INSERT INTO project_challenges
                (month, title, description, requirements, deadline)
                VALUES (?, ?, ?, ?, ?)
                """,
                (month, title, description, requirements, deadline),
            )

            result = self.database.query_one(
                "SELECT * FROM project_challenges ORDER BY id DESC LIMIT 1"
            )

            logger.info(f"Challenge created: {title}")
            return result

        except Exception as exc:
            logger.error(f"Failed to create challenge: {exc}")
            return None

    def get_challenge(self, month: str) -> Optional[Dict[str, Any]]:
        """Get current month challenge."""
        if not self.database:
            return None

        try:
            return self.database.query_one(
                """
                SELECT * FROM project_challenges
                WHERE month = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (month,),
            )
        except Exception as exc:
            logger.error(f"Failed to get challenge: {exc}")
            return None

    def get_all_challenges(self) -> List[Dict[str, Any]]:
        """Get all challenges."""
        if not self.database:
            return []

        try:
            return self.database.query(
                "SELECT * FROM project_challenges ORDER BY id DESC"
            )
        except Exception as exc:
            logger.error(f"Failed to get challenges: {exc}")
            return []

    # ========================================================
    # SUBMISSIONS
    # ========================================================

    def submit_project(
        self,
        user_id: str,
        month: str,
        project_repo: str = "",
        video_link: str = "",
        challenge_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Submit a student project."""
        if not self.database:
            return None

        try:
            self.database.execute(
                """
                INSERT INTO student_submissions
                (user_id, month, challenge_id, project_repo, video_link)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, month, challenge_id, project_repo, video_link),
            )

            result = self.database.query_one(
                "SELECT * FROM student_submissions ORDER BY id DESC LIMIT 1"
            )

            logger.info(f"Project submitted by {user_id}")
            return result

        except Exception as exc:
            logger.error(f"Failed to submit project: {exc}")
            return None

    def get_submissions(
        self,
        month: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get submissions with optional filters."""
        if not self.database:
            return []

        try:
            if month and status:
                return self.database.query(
                    """
                    SELECT * FROM student_submissions
                    WHERE month = ? AND review_status = ?
                    ORDER BY submission_date DESC
                    """,
                    (month, status),
                )
            elif month:
                return self.database.query(
                    """
                    SELECT * FROM student_submissions
                    WHERE month = ?
                    ORDER BY submission_date DESC
                    """,
                    (month,),
                )
            elif status:
                return self.database.query(
                    """
                    SELECT * FROM student_submissions
                    WHERE review_status = ?
                    ORDER BY submission_date DESC
                    """,
                    (status,),
                )
            else:
                return self.database.query(
                    "SELECT * FROM student_submissions ORDER BY submission_date DESC"
                )
        except Exception as exc:
            logger.error(f"Failed to get submissions: {exc}")
            return []

    def get_pending_submissions(self) -> List[Dict[str, Any]]:
        """Get submissions pending review."""
        return self.get_submissions(status="pending")

    # ========================================================
    # REVIEW WORKFLOW
    # ========================================================

    def review_submission(
        self,
        submission_id: int,
        reviewer: str,
        status: str,
        feedback: str = "",
    ) -> bool:
        """
        Review a submission.
        status: 'passed' or 'failed'
        """
        if not self.database:
            return False

        if status not in ("passed", "failed"):
            logger.error(f"Invalid review status: {status}")
            return False

        try:
            self.database.execute(
                """
                UPDATE student_submissions
                SET review_status = ?,
                    feedback = ?,
                    reviewed_by = ?,
                    reviewed_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, feedback, reviewer, submission_id),
            )

            logger.info(f"Submission #{submission_id} reviewed: {status}")
            return True

        except Exception as exc:
            logger.error(f"Failed to review submission: {exc}")
            return False

    def approve_submission(self, submission_id: int, reviewer: str, feedback: str = "") -> bool:
        """Approve a submission."""
        return self.review_submission(submission_id, reviewer, "passed", feedback)

    def reject_submission(self, submission_id: int, reviewer: str, feedback: str = "") -> bool:
        """Reject a submission."""
        return self.review_submission(submission_id, reviewer, "failed", feedback)

    # ========================================================
    # STATISTICS
    # ========================================================

    def get_submission_stats(self, month: str) -> Dict[str, Any]:
        """Get submission statistics for a month."""
        if not self.database:
            return {}

        try:
            row = self.database.query_one(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN review_status='passed' THEN 1 ELSE 0 END) AS passed,
                    SUM(CASE WHEN review_status='failed' THEN 1 ELSE 0 END) AS failed,
                    SUM(CASE WHEN review_status='pending' THEN 1 ELSE 0 END) AS pending
                FROM student_submissions
                WHERE month = ?
                """,
                (month,),
            )

            return {
                "total": int((row or {}).get("total", 0) or 0),
                "passed": int((row or {}).get("passed", 0) or 0),
                "failed": int((row or {}).get("failed", 0) or 0),
                "pending": int((row or {}).get("pending", 0) or 0),
            }

        except Exception as exc:
            logger.error(f"Failed to get stats: {exc}")
            return {}


# ============================================================
# FACTORY
# ============================================================

def create_student_system(
    config: Optional[Config] = None,
    database: Optional[DatabaseInterface] = None,
) -> StudentSystem:
    """Factory function for StudentSystem."""
    return StudentSystem(
        config=config,
        database=database,
    )
