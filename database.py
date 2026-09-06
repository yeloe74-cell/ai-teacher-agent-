# database.py
"""
Database layer for AI Teacher Bot.
Provides a clean interface for data persistence.

Supports:
- SQLite (development/testing)
- Cloudflare D1 (production)
"""

import sqlite3
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================
# EXCEPTIONS
# ============================================================

class DatabaseError(Exception):
    """Base exception for database errors."""
    pass


class DatabaseConnectionError(DatabaseError):
    """Raised when database connection fails."""
    pass


class DatabaseQueryError(DatabaseError):
    """Raised when database query fails."""
    pass


# ============================================================
# ABSTRACT INTERFACE
# ============================================================

class DatabaseInterface(ABC):
    """
    Abstract base class for database operations.
    
    All database implementations must provide these methods.
    This allows switching between SQLite and D1 without
    changing business logic.
    """

    @abstractmethod
    def execute(self, query: str, params: tuple = ()) -> int:
        """Execute a write query. Returns last row ID."""
        pass

    @abstractmethod
    def query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Execute a read query. Returns list of dictionaries."""
        pass

    @abstractmethod
    def query_one(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """Execute a read query. Returns first row or None."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close database connection."""
        pass


# ============================================================
# SQLite IMPLEMENTATION
# ============================================================

class SQLiteDatabase(DatabaseInterface):
    """
    SQLite database implementation.
    Used for local development and testing.
    """

    def __init__(self, db_path: str = "data/app.db", timeout: int = 30):
        """
        Initialize SQLite database.
        
        Args:
            db_path: Path to SQLite database file.
            timeout: Connection timeout in seconds.
        """
        self.db_path = db_path
        self.timeout = timeout
        self.conn: Optional[sqlite3.Connection] = None
        self._connect()
        self._init_tables()
        logger.info(f"SQLite database ready at {db_path}")

    def _connect(self) -> None:
        """Establish database connection."""
        try:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

            self.conn = sqlite3.connect(self.db_path, timeout=self.timeout)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA foreign_keys=ON")
            self.conn.execute("PRAGMA busy_timeout=5000")

            logger.debug(f"Connected to SQLite: {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"SQLite connection failed: {e}")
            raise DatabaseConnectionError(f"Connection failed: {e}")

    def _init_tables(self) -> None:
        """Create database tables if they don't exist."""
        schema = self._get_schema()
        try:
            with self.conn:
                self.conn.executescript(schema)
            logger.debug("Database tables created/verified")
        except sqlite3.Error as e:
            logger.error(f"Table creation failed: {e}")
            raise DatabaseError(f"Table creation failed: {e}")

    def _get_schema(self) -> str:
        """Get database schema SQL."""
        return """
        CREATE TABLE IF NOT EXISTS curriculum (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month TEXT UNIQUE NOT NULL,
            language TEXT NOT NULL,
            description TEXT,
            total_days INTEGER DEFAULT 30,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS lessons (
            id TEXT PRIMARY KEY,
            month TEXT NOT NULL,
            day_number INTEGER NOT NULL,
            lesson_type TEXT NOT NULL,
            topic TEXT NOT NULL,
            content TEXT,
            status TEXT DEFAULT 'pending',
            telegram_message_id TEXT,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            published_at TIMESTAMP,
            UNIQUE(month, day_number, lesson_type)
        );

        CREATE TABLE IF NOT EXISTS groups (
            id TEXT PRIMARY KEY,
            group_id TEXT UNIQUE NOT NULL,
            group_title TEXT,
            status TEXT DEFAULT 'pending',
            auto_share INTEGER DEFAULT 0,
            enabled INTEGER DEFAULT 1,
            added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_share_date TIMESTAMP,
            daily_share_count INTEGER DEFAULT 0,
            total_shares INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS shared_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_id TEXT NOT NULL,
            channel_message_id TEXT NOT NULL,
            group_id TEXT NOT NULL,
            group_message_id TEXT,
            status TEXT DEFAULT 'shared',
            shared_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(lesson_id, group_id),
            FOREIGN KEY (lesson_id) REFERENCES lessons(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS published_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_id TEXT NOT NULL,
            channel_message_id TEXT NOT NULL,
            published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lesson_id) REFERENCES lessons(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            command TEXT NOT NULL,
            executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS app_state (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS found_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link TEXT UNIQUE NOT NULL,
            source_group_id TEXT,
            status TEXT DEFAULT 'found',
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposal_type TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_by TEXT DEFAULT 'agent',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_by TEXT,
            reviewed_at TIMESTAMP,
            review_notes TEXT
        );

        CREATE TABLE IF NOT EXISTS agent_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_type TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS student_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            feedback_type TEXT,
            content TEXT,
            rating INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS project_challenges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            requirements TEXT NOT NULL,
            deadline TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS student_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            month TEXT NOT NULL,
            challenge_id INTEGER,
            project_repo TEXT,
            video_link TEXT,
            submission_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            review_status TEXT DEFAULT 'pending',
            feedback TEXT,
            reviewed_by TEXT,
            reviewed_at TIMESTAMP,
            FOREIGN KEY (challenge_id) REFERENCES project_challenges(id)
        );

        CREATE INDEX IF NOT EXISTS idx_lessons_month ON lessons(month);
        CREATE INDEX IF NOT EXISTS idx_lessons_status ON lessons(status);
        CREATE INDEX IF NOT EXISTS idx_groups_status ON groups(status);
        CREATE INDEX IF NOT EXISTS idx_groups_auto_share ON groups(auto_share);
        CREATE INDEX IF NOT EXISTS idx_groups_enabled ON groups(enabled);
        CREATE INDEX IF NOT EXISTS idx_shared_posts_lesson ON shared_posts(lesson_id);
        CREATE INDEX IF NOT EXISTS idx_shared_posts_group ON shared_posts(group_id);
        CREATE INDEX IF NOT EXISTS idx_found_links_status ON found_links(status);
        """

    def execute(self, query: str, params: tuple = ()) -> int:
        """Execute a write query."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(query, params)
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Execute failed: {e}")
            raise DatabaseQueryError(f"Execute failed: {e}")

    def query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Execute a read query and return all rows."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Query failed: {e}")
            raise DatabaseQueryError(f"Query failed: {e}")

    def query_one(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """Execute a read query and return first row."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as e:
            logger.error(f"Query one failed: {e}")
            raise DatabaseQueryError(f"Query one failed: {e}")

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("SQLite connection closed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# ============================================================
# FACTORY
# ============================================================

def create_database(config) -> DatabaseInterface:
    """
    Factory function to create appropriate database instance.
    
    Args:
        config: Config instance.
    
    Returns:
        DatabaseInterface implementation.
    """
    return SQLiteDatabase(
        db_path=config.sqlite_db_path,
        timeout=config.db_timeout,
    )
