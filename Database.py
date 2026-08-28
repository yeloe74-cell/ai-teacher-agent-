database.py

"""
Database layer for AI Teacher Bot.
Provides a clean interface for data persistence.

Supports:

SQLite (development/testing)

Cloudflare D1 (production)


Architecture:

DatabaseInterface: Abstract base class

SQLiteDatabase: SQLite implementation

D1Database: Cloudflare D1 REST API implementation

create_database(): Factory function


Future modules (Part 3-10) should use DatabaseInterface
rather than concrete implementations for better testability.
"""
import os
import json
import sqlite3
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional
from contextlib import contextmanager

logger = logging.getLogger(name)

class DatabaseError(Exception):
"""Base exception for database errors."""
pass

class DatabaseConnectionError(DatabaseError):
"""Raised when database connection fails."""
pass

class DatabaseQueryError(DatabaseError):
"""Raised when database query fails."""
pass

class DatabaseInterface(ABC):
"""
Abstract base class for database operations.

All database implementations must provide these methods.  
This allows switching between SQLite and D1 without  
changing business logic.  
"""  
  
@abstractmethod  
def execute(self, query: str, params: tuple = ()) -> int:  
    """  
    Execute a write query (INSERT, UPDATE, DELETE).  
      
    Args:  
        query: SQL query string  
        params: Query parameters  
      
    Returns:  
        Last row ID  
    """  
    pass  
  
@abstractmethod  
def query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:  
    """  
    Execute a read query and return all rows.  
      
    Args:  
        query: SQL query string  
        params: Query parameters  
      
    Returns:  
        List of dictionaries  
    """  
    pass  
  
@abstractmethod  
def query_one(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:  
    """  
    Execute a read query and return first row.  
      
    Args:  
        query: SQL query string  
        params: Query parameters  
      
    Returns:  
        Dictionary or None  
    """  
    pass  
  
@abstractmethod  
def close(self) -> None:  
    """Close database connection."""  
    pass

class SQLiteDatabase(DatabaseInterface):
"""
SQLite database implementation.
Used for local development and testing.
"""

def __init__(self, db_path: str = "data/app.db", timeout: int = 30):  
    """  
    Initialize SQLite database.  
      
    Args:  
        db_path: Path to SQLite database file  
        timeout: Connection timeout in seconds  
      
    Raises:  
        DatabaseConnectionError: If connection fails  
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
        # Create directory if needed  
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)  
          
        # Connect to database  
        self.conn = sqlite3.connect(  
            self.db_path,  
            timeout=self.timeout  
        )  
        self.conn.row_factory = sqlite3.Row  
        self.conn.execute("PRAGMA journal_mode=WAL")  
        self.conn.execute("PRAGMA foreign_keys=ON")  
        self.conn.execute("PRAGMA busy_timeout=5000")  
          
        logger.debug(f"Connected to SQLite at {self.db_path}")  
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
        daily_share_count INTEGER DEFAULT 0  
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
      
    CREATE INDEX IF NOT EXISTS idx_lessons_month ON lessons(month);  
    CREATE INDEX IF NOT EXISTS idx_lessons_status ON lessons(status);  
    CREATE INDEX IF NOT EXISTS idx_groups_status ON groups(status);  
    """  
  
@contextmanager  
def transaction(self):  
    """  
    Context manager for database transactions.  
    Automatically commits or rolls back.  
    """  
    try:  
        yield self.conn  
        self.conn.commit()  
    except Exception as e:  
        self.conn.rollback()  
        logger.error(f"Transaction failed: {e}")  
        raise  
  
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
        logger.info("SQLite connection closed")  
  
def __enter__(self):  
    return self  
  
def __exit__(self, exc_type, exc_val, exc_tb):  
    self.close()

class D1Database(DatabaseInterface):
"""
Cloudflare D1 database implementation.
Uses REST API for database operations.
"""

def __init__(  
    self,  
    account_id: str,  
    api_token: str,  
    database_id: str,  
    timeout: int = 30  
):  
    """  
    Initialize D1 database client.  
      
    Args:  
        account_id: Cloudflare account ID  
        api_token: Cloudflare API token  
        database_id: D1 database ID  
        timeout: Request timeout in seconds  
    """  
    self.account_id = account_id  
    self.api_token = api_token  
    self.database_id = database_id  
    self.timeout = timeout  
    self.base_url = (  
        f"https://api.cloudflare.com/client/v4/accounts/"  
        f"{account_id}/d1/database/{database_id}"  
    )  
    logger.info("D1 database client initialized")  
  
def _make_request(self, query: str, params: tuple = ()) -> Dict[str, Any]:  
    """  
    Make D1 API request.  
      
    Args:  
        query: SQL query  
        params: Query parameters  
      
    Returns:  
        API response  
      
    Raises:  
        DatabaseError: If API request fails  
    """  
    import requests  
      
    headers = {  
        "Authorization": f"Bearer {self.api_token}",  
        "Content-Type": "application/json",  
    }  
      
    payload = {  
        "sql": query,  
        "params": list(params),  
    }  
      
    try:  
        response = requests.post(  
            f"{self.base_url}/query",  
            headers=headers,  
            json=payload,  
            timeout=self.timeout,  
        )  
        response.raise_for_status()  
        result = response.json()  
          
        if not result.get("success", False):  
            errors = result.get("errors", [])  
            error_msg = (  
                errors[0].get("message", "Unknown D1 error")  
                if errors else "Unknown D1 error"  
            )  
            raise DatabaseError(f"D1 API error: {error_msg}")  
          
        return result  
          
    except requests.RequestException as e:  
        logger.error(f"D1 request failed: {e}")  
        raise DatabaseError(f"D1 request failed: {e}")  
  
def execute(self, query: str, params: tuple = ()) -> int:  
    """Execute a write query."""  
    result = self._make_request(query, params)  
    meta = result.get("result", [{}])[0].get("meta", {})  
    return int(meta.get("last_row_id", 0))  
  
def query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:  
    """Execute a read query and return all rows."""  
    result = self._make_request(query, params)  
    rows = result.get("result", [{}])[0].get("results", [])  
    return rows  
  
def query_one(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:  
    """Execute a read query and return first row."""  
    rows = self.query(query, params)  
    return rows[0] if rows else None  
  
def close(self) -> None:  
    """D1 doesn't maintain persistent connections."""  
    pass

def create_database(config) -> DatabaseInterface:
"""
Factory function to create appropriate database instance.

Args:  
    config: Config instance  
  
Returns:  
    DatabaseInterface implementation  
  
Raises:  
    DatabaseError: If D1 configuration is incomplete  
"""  
if config.db_backend == "d1":  
    if not config.cf_d1_database_id:  
        raise DatabaseError("D1 backend selected but CF_D1_DATABASE_ID missing")  
    return D1Database(  
        account_id=config.cf_account_id,  
        api_token=config.cf_api_token,  
        database_id=config.cf_d1_database_id,  
        timeout=config.db_timeout,  
    )  
else:  
    return SQLiteDatabase(  
        db_path=config.sqlite_db_path,  
        timeout=config.db_timeout,  
)
