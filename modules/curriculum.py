"""
Curriculum Manager

Responsibilities:
- Load curriculum JSON files
- Validate curriculum structure
- Cache loaded curricula
- Provide daily lesson topics
- Support curriculum reload
- Provide safe read-only access

Important:
The curriculum manager does NOT allow the AI agent to directly
modify curriculum files.

Future versions may add:
    AI Agent
        ↓
    Curriculum Proposal
        ↓
    Owner Approval
        ↓
    Curriculum Manager
        ↓
    Save new curriculum

This keeps AI autonomy separate from owner authority.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


# ================================================================
# EXCEPTIONS
# ================================================================

class CurriculumError(Exception):
    """Base exception for curriculum-related errors."""
    pass


class CurriculumFileNotFoundError(CurriculumError):
    """Raised when a curriculum JSON file does not exist."""
    pass


class CurriculumValidationError(CurriculumError):
    """Raised when curriculum structure is invalid."""
    pass


# ================================================================
# CURRICULUM MANAGER
# ================================================================

class Curriculum:
    """
    Curriculum loader and manager.

    Alpha responsibilities:
        - Load JSON curriculum files
        - Validate data
        - Cache loaded curriculum
        - Retrieve day/topic information
        - Reload curriculum when needed

    The manager is intentionally read-focused.

    AI agents must NOT directly modify curriculum files.
    """

    VALID_LESSON_TYPES = {
        "morning_lesson",
        "evening_practice",
    }

    MIN_DAY = 1
    MAX_DAY = 31

    def __init__(self, data_dir: str = "data"):
        """
        Initialize curriculum manager.

        Args:
            data_dir: Directory containing curriculum JSON files.
        """
        self.data_dir = Path(data_dir)
        self.curriculum: Dict[str, Dict[str, Any]] = {}

        logger.debug(
            "Curriculum manager initialized: %s",
            self.data_dir,
        )

    # ============================================================
    # FILE PATH
    # ============================================================

    def _get_file_path(self, month: str) -> Path:
        """
        Build curriculum file path safely.

        Args:
            month: Curriculum identifier.

        Returns:
            Path to curriculum JSON file.

        Raises:
            CurriculumError: If month identifier is invalid.
        """
        if not month or not isinstance(month, str):
            raise CurriculumError(
                "Month identifier must be a non-empty string"
            )

        # Prevent accidental path traversal.
        if "/" in month or "\\" in month or ".." in month:
            raise CurriculumError(
                f"Invalid curriculum identifier: {month}"
            )

        return self.data_dir / f"{month}.json"

    # ============================================================
    # VALIDATION
    # ============================================================

    def _validate_curriculum(
        self,
        data: Any,
        month: str,
    ) -> Dict[str, Any]:
        """
        Validate curriculum JSON structure.

        Required structure:

            {
                "month": "...",
                "language": "...",
                "description": "...",
                "total_days": 30,
                "days": [...]
            }

        Args:
            data: Parsed JSON data.
            month: Expected month identifier.

        Returns:
            Validated curriculum dictionary.

        Raises:
            CurriculumValidationError:
                If curriculum structure is invalid.
        """

        if not isinstance(data, dict):
            raise CurriculumValidationError(
                f"Curriculum must be a JSON object: {month}"
            )

        # --------------------------------------------------------
        # Required metadata
        # --------------------------------------------------------

        required_fields = (
            "month",
            "language",
            "description",
            "total_days",
            "days",
        )

        for field in required_fields:
            if field not in data:
                raise CurriculumValidationError(
                    f"Missing required field '{field}': {month}"
                )

        # --------------------------------------------------------
        # Month validation
        # --------------------------------------------------------

        if data["month"] != month:
            raise CurriculumValidationError(
                f"Month mismatch: filename={month}, "
                f"json={data['month']}"
            )

        # --------------------------------------------------------
        # Basic field validation
        # --------------------------------------------------------

        if not isinstance(data["language"], str) or not data["language"].strip():
            raise CurriculumValidationError(
                f"Invalid language field: {month}"
            )

        if not isinstance(data["description"], str):
            raise CurriculumValidationError(
                f"Invalid description field: {month}"
            )

        # --------------------------------------------------------
        # Total days validation
        # --------------------------------------------------------

        total_days = data["total_days"]

        if (
            not isinstance(total_days, int)
            or isinstance(total_days, bool)
            or total_days < 1
            or total_days > self.MAX_DAY
        ):
            raise CurriculumValidationError(
                f"Invalid total_days={total_days}: {month}"
            )

        # --------------------------------------------------------
        # Days validation
        # --------------------------------------------------------

        days = data["days"]

        if not isinstance(days, list):
            raise CurriculumValidationError(
                f"'days' must be a list: {month}"
            )

        if len(days) != total_days:
            raise CurriculumValidationError(
                f"total_days={total_days}, "
                f"but found {len(days)} day entries: {month}"
            )

        seen_days = set()

        for index, day_data in enumerate(days, start=1):

            if not isinstance(day_data, dict):
                raise CurriculumValidationError(
                    f"Day entry #{index} must be an object: {month}"
                )

            # ----------------------------------------------------
            # Day number
            # ----------------------------------------------------

            if "day" not in day_data:
                raise CurriculumValidationError(
                    f"Missing day number in entry #{index}: {month}"
                )

            day_number = day_data["day"]

            if (
                not isinstance(day_number, int)
                or isinstance(day_number, bool)
                or day_number < self.MIN_DAY
                or day_number > total_days
            ):
                raise CurriculumValidationError(
                    f"Invalid day number {day_number}: {month}"
                )

            if day_number in seen_days:
                raise CurriculumValidationError(
                    f"Duplicate day number {day_number}: {month}"
                )

            seen_days.add(day_number)

            # ----------------------------------------------------
            # Lesson topics
            # ----------------------------------------------------

            for lesson_type in self.VALID_LESSON_TYPES:

                if lesson_type not in day_data:
                    raise CurriculumValidationError(
                        f"Missing '{lesson_type}' "
                        f"for Day {day_number}: {month}"
                    )

                topic = day_data[lesson_type]

                if (
                    not isinstance(topic, str)
                    or not topic.strip()
                ):
                    raise CurriculumValidationError(
                        f"Invalid topic for Day {day_number} "
                        f"({lesson_type}): {month}"
                    )

        # --------------------------------------------------------
        # Ensure all days exist
        # --------------------------------------------------------

        expected_days = set(range(1, total_days + 1))

        if seen_days != expected_days:
            missing = sorted(expected_days - seen_days)

            raise CurriculumValidationError(
                f"Missing day entries {missing}: {month}"
            )

        return data

    # ============================================================
    # LOAD
    # ============================================================

    def load_curriculum(
        self,
        month: str,
        force_reload: bool = False,
    ) -> Dict[str, Any]:
        """
        Load curriculum for a specific month.

        Args:
            month: Curriculum identifier.
            force_reload: Reload even if already cached.

        Returns:
            Validated curriculum dictionary.

        Raises:
            CurriculumFileNotFoundError:
                If file does not exist.
            CurriculumValidationError:
                If JSON/data structure is invalid.
            CurriculumError:
                For other loading errors.
        """

        if not force_reload and month in self.curriculum:
            return self.curriculum[month]

        file_path = self._get_file_path(month)

        if not file_path.exists():
            raise CurriculumFileNotFoundError(
                f"Curriculum file not found: {file_path}"
            )

        if not file_path.is_file():
            raise CurriculumFileNotFoundError(
                f"Curriculum path is not a file: {file_path}"
            )

        try:
            with file_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(file)

        except json.JSONDecodeError as e:
            raise CurriculumValidationError(
                f"Invalid JSON in {file_path}: {e}"
            ) from e

        except OSError as e:
            raise CurriculumError(
                f"Failed to read curriculum {file_path}: {e}"
            ) from e

        # Validate before caching.
        validated = self._validate_curriculum(
            data,
            month,
        )

        self.curriculum[month] = validated

        logger.info(
            "Curriculum loaded: %s (%d days)",
            month,
            validated["total_days"],
        )

        return validated

    # ============================================================
    # RELOAD
    # ============================================================

    def reload_curriculum(
        self,
        month: str,
    ) -> Dict[str, Any]:
        """
        Force reload curriculum from disk.

        Useful after an approved curriculum update.

        Args:
            month: Curriculum identifier.

        Returns:
            Reloaded curriculum.
        """
        logger.info(
            "Reloading curriculum: %s",
            month,
        )

        return self.load_curriculum(
            month,
            force_reload=True,
        )

    # ============================================================
    # GET DAY
    # ============================================================

    def get_day_data(
        self,
        month: str,
        day_number: int,
    ) -> Dict[str, Any]:
        """
        Get curriculum data for a specific day.

        Args:
            month: Curriculum identifier.
            day_number: Day number.

        Returns:
            Day data dictionary.
        """

        if (
            not isinstance(day_number, int)
            or isinstance(day_number, bool)
            or day_number < self.MIN_DAY
            or day_number > self.MAX_DAY
        ):
            raise CurriculumError(
                f"Invalid day number: {day_number}"
            )

        curriculum = self.load_curriculum(month)

        for day_data in curriculum["days"]:
            if day_data["day"] == day_number:
                return day_data

        raise CurriculumError(
            f"Day {day_number} not found in {month}"
        )

    # ============================================================
    # GET TOPIC
    # ============================================================

    def get_topic(
        self,
        month: str,
        day_number: int,
        lesson_type: str,
    ) -> str:
        """
        Get a lesson topic.

        Args:
            month: Curriculum identifier.
            day_number: Day number.
            lesson_type:
                morning_lesson
                evening_practice

        Returns:
            Lesson topic.
        """

        if lesson_type not in self.VALID_LESSON_TYPES:
            raise CurriculumError(
                f"Invalid lesson type: {lesson_type}"
            )

        day_data = self.get_day_data(
            month,
            day_number,
        )

        topic = day_data.get(lesson_type)

        if not topic:
            raise CurriculumError(
                f"Topic not found for "
                f"{month} Day {day_number} "
                f"({lesson_type})"
            )

        return topic

    # ============================================================
    # GET TOTAL DAYS
    # ============================================================

    def get_total_days(
        self,
        month: str,
    ) -> int:
        """
        Get total number of days.

        Args:
            month: Curriculum identifier.

        Returns:
            Total days.
        """

        curriculum = self.load_curriculum(month)

        return curriculum["total_days"]

    # ============================================================
    # GET ALL DAYS
    # ============================================================

    def get_all_days(
        self,
        month: str,
    ) -> List[Dict[str, Any]]:
        """
        Get all curriculum days.

        Args:
            month: Curriculum identifier.

        Returns:
            List of day dictionaries.
        """

        curriculum = self.load_curriculum(month)

        # Return a copy so callers don't accidentally
        # modify the cached curriculum.
        return list(curriculum["days"])

    # ============================================================
    # GET METADATA
    # ============================================================

    def get_metadata(
        self,
        month: str,
    ) -> Dict[str, Any]:
        """
        Get curriculum metadata.

        Returns:
            Dictionary containing month, language,
            description and total_days.
        """

        curriculum = self.load_curriculum(month)

        return {
            "month": curriculum["month"],
            "language": curriculum["language"],
            "description": curriculum["description"],
            "total_days": curriculum["total_days"],
        }

    # ============================================================
    # CHECK DAY
    # ============================================================

    def has_day(
        self,
        month: str,
        day_number: int,
    ) -> bool:
        """
        Check whether a day exists.

        Returns:
            True if day exists, otherwise False.
        """

        try:
            self.get_day_data(
                month,
                day_number,
            )
            return True

        except CurriculumError:
            return False

    # ============================================================
    # CLEAR CACHE
    # ============================================================

    def clear_cache(
        self,
        month: Optional[str] = None,
    ) -> None:
        """
        Clear curriculum cache.

        Args:
            month:
                Clear only this month if provided.
                Clear everything if None.
        """

        if month is None:
            self.curriculum.clear()

            logger.debug(
                "All curriculum cache cleared"
            )

            return

        self.curriculum.pop(month, None)

        logger.debug(
            "Curriculum cache cleared: %s",
            month,
        )


# ================================================================
# SINGLETON
# ================================================================

curriculum_manager = Curriculum()
