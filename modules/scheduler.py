# modules/scheduler.py
"""
Scheduler for AI Teacher Bot.
Uses APScheduler for automated daily posting.
"""

import logging
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config import Config, get_config
from database import DatabaseInterface
from modules.curriculum import Curriculum, curriculum_manager
from modules.publisher import Publisher, create_publisher

logger = logging.getLogger(__name__)


class LessonScheduler:
    """
    Scheduler for daily lessons.

    Handles:
    - Morning lesson scheduling
    - Evening practice scheduling
    - Current day tracking
    - Duplicate prevention
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        curriculum: Optional[Curriculum] = None,
        publisher: Optional[Publisher] = None,
    ):
        """
        Initialize scheduler.

        Args:
            config: Config instance.
            curriculum: Curriculum manager.
            publisher: Publisher instance.
        """
        self.config = config or get_config()
        self.curriculum = curriculum or curriculum_manager
        self.publisher = publisher or create_publisher(self.config)

        # APScheduler instance
        self.scheduler = BlockingScheduler(timezone=self.config.timezone)

        # Current state
        self.current_month = self._get_current_month()
        self.current_day = self._get_current_day_from_db()

        logger.debug("LessonScheduler initialized")

    def _get_current_month(self) -> str:
        """
        Get current month identifier.

        For now, hardcoded to "python_month_1".
        Will be configurable in future versions.

        Returns:
            Month identifier.
        """
        return "python_month_1"

    def _get_current_day_from_db(self) -> int:
        """
        Get current day from database.

        Checks the latest published lesson to determine current day.
        If no lessons published yet, start from day 1.

        Returns:
            Current day number.
        """
        try:
            result = self.publisher.database.query_one("""
                SELECT day_number
                FROM lessons
                WHERE status = 'published'
                ORDER BY published_at DESC
                LIMIT 1
                """)

            if result and result.get("day_number"):
                return int(result["day_number"])

            return 1

        except Exception as e:
            logger.warning(f"Failed to get current day from DB: {e}")
            return 1

    def _publish_morning_lesson(self) -> None:
        """
        Publish morning lesson for current day.
        """
        logger.info(f"Publishing morning lesson: Day {self.current_day}")

        try:
            topic = self.curriculum.get_topic(
                self.current_month,
                self.current_day,
                "morning_lesson",
            )

            result = self.publisher.publish_lesson(
                topic=topic,
                lesson_type="morning_lesson",
                month=self.current_month,
                day_number=self.current_day,
            )

            if result:
                logger.info(f"Morning lesson published: Day {self.current_day}")
            else:
                logger.warning(
                    f"Morning lesson skipped or failed: Day {self.current_day}"
                )

        except Exception as e:
            logger.error(f"Failed to publish morning lesson: {e}")

    def _publish_evening_practice(self) -> None:
        """
        Publish evening practice for current day.
        """
        logger.info(f"Publishing evening practice: Day {self.current_day}")

        try:
            topic = self.curriculum.get_topic(
                self.current_month,
                self.current_day,
                "evening_practice",
            )

            result = self.publisher.publish_lesson(
                topic=topic,
                lesson_type="evening_practice",
                month=self.current_month,
                day_number=self.current_day,
            )

            if result:
                logger.info(f"Evening practice published: Day {self.current_day}")
                # Move to next day after evening practice succeeds
                self._advance_day()
            else:
                logger.warning(
                    f"Evening practice skipped or failed: Day {self.current_day}"
                )

        except Exception as e:
            logger.error(f"Failed to publish evening practice: {e}")

    def _advance_day(self) -> None:
        """
        Advance to next day.
        """
        total_days = self.curriculum.get_total_days(self.current_month)

        if self.current_day >= total_days:
            logger.info("Curriculum completed!")
            self.current_day = 1  # Reset or stop
        else:
            self.current_day += 1
            logger.info(f"Advanced to Day {self.current_day}")

    def setup_jobs(self) -> None:
        """
        Setup scheduled jobs.
        """
        # Parse time strings
        morning_time = self.config.morning_post_time
        evening_time = self.config.evening_post_time

        morning_hour, morning_minute = self._parse_time(morning_time)
        evening_hour, evening_minute = self._parse_time(evening_time)

        # Morning lesson job
        self.scheduler.add_job(
            self._publish_morning_lesson,
            trigger=CronTrigger(
                hour=morning_hour,
                minute=morning_minute,
                timezone=self.config.timezone,
            ),
            id="morning_lesson",
            name="Morning Lesson Publisher",
            replace_existing=True,
        )

        # Evening practice job
        self.scheduler.add_job(
            self._publish_evening_practice,
            trigger=CronTrigger(
                hour=evening_hour,
                minute=evening_minute,
                timezone=self.config.timezone,
            ),
            id="evening_practice",
            name="Evening Practice Publisher",
            replace_existing=True,
        )

        logger.info(
            f"Scheduled: Morning at {morning_time}, Evening at {evening_time} "
            f"(Timezone: {self.config.timezone})"
        )

    @staticmethod
    def _parse_time(time_str: str) -> tuple:
        """
        Parse "HH:MM" string to (hour, minute).

        Args:
            time_str: Time string.

        Returns:
            Tuple of (hour, minute).
        """
        try:
            hour, minute = time_str.split(":")
            return int(hour), int(minute)
        except (ValueError, AttributeError) as e:
            logger.error(f"Invalid time format: {time_str}")
            return 8, 0  # Default 8:00 AM

    def start(self) -> None:
        """
        Start scheduler.
        """
        self.setup_jobs()
        logger.info("Scheduler started. Press Ctrl+C to stop.")

        try:
            self.scheduler.start()
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
        finally:
            self.publisher.close()

    def run_once(self, lesson_type: str = "morning_lesson") -> None:
        """
        Run a single lesson immediately.
        Useful for testing.

        Args:
            lesson_type: "morning_lesson" or "evening_practice".
        """
        if lesson_type == "morning_lesson":
            self._publish_morning_lesson()
        elif lesson_type == "evening_practice":
            self._publish_evening_practice()
        else:
            logger.error(f"Unknown lesson type: {lesson_type}")


def create_scheduler(config: Optional[Config] = None) -> LessonScheduler:
    """
    Factory function for LessonScheduler.
    """
    return LessonScheduler(config=config)
