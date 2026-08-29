# scripts/run_migrations.py
"""
Database Migration Runner

Handles:
- Safe transaction management
- SQLite executescript compatibility
- Idempotent migrations
- D1 compatibility
"""

import logging
import sqlite3
import sys
from pathlib import Path
from typing import List, Set


# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """Setup basic console logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )


# ============================================================
# CONFIG
# ============================================================

def get_db_path() -> str:
    """Get SQLite database path from application config."""
    from config import get_config
    config = get_config()
    return config.sqlite_db_path


# ============================================================
# MIGRATION FILES
# ============================================================

def get_migration_files(migrations_dir: Path) -> List[Path]:
    """Get migration SQL files sorted by filename."""
    if not migrations_dir.exists():
        logger.warning(f"Migrations directory not found: {migrations_dir}")
        return []

    files = sorted(migrations_dir.glob("*.sql"))
    logger.debug(f"Found {len(files)} migration file(s)")
    return files


# ============================================================
# MIGRATION TRACKING TABLE
# ============================================================

def init_migrations_table(conn: sqlite3.Connection) -> None:
    """Create schema_migrations table if it does not exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()


def get_applied_migrations(conn: sqlite3.Connection) -> Set[str]:
    """Get filenames of already applied migrations."""
    cursor = conn.execute(
        """
        SELECT filename
        FROM schema_migrations
        ORDER BY id
        """
    )
    rows = cursor.fetchall()
    return {row[0] for row in rows}


# ============================================================
# SAFE ALTER TABLE
# ============================================================

def column_exists(
    conn: sqlite3.Connection,
    table: str,
    column: str,
) -> bool:
    """
    Check if a column exists in a table.
    
    Args:
        conn: SQLite connection.
        table: Table name.
        column: Column name.
    
    Returns:
        True if column exists.
    """
    cursor = conn.execute(f"PRAGMA table_info({table})")
    columns = cursor.fetchall()
    return any(col[1] == column for col in columns)


def safe_add_column(
    conn: sqlite3.Connection,
    table: str,
    column: str,
    column_type: str,
    default_value: str = None,
) -> bool:
    """
    Safely add a column to a table.
    Checks if column exists first to avoid duplicate errors.
    
    Args:
        conn: SQLite connection.
        table: Table name.
        column: Column name.
        column_type: Column type.
        default_value: Default value.
    
    Returns:
        True if column was added, False if already exists.
    """
    if column_exists(conn, table, column):
        logger.info(f"Column already exists: {table}.{column}")
        return False
    
    sql = f"ALTER TABLE {table} ADD COLUMN {column} {column_type}"
    
    if default_value is not None:
        sql += f" DEFAULT {default_value}"
    
    conn.execute(sql)
    conn.commit()
    
    logger.info(f"Added column: {table}.{column}")
    return True


# ============================================================
# APPLY MIGRATION
# ============================================================

def apply_migration(
    conn: sqlite3.Connection,
    file_path: Path,
) -> None:
    """
    Apply one SQL migration.
    
    Migration is executed inside a transaction.
    If migration fails:
        - Changes are rolled back.
        - Migration is NOT recorded.
        - Exception is raised.
    
    Args:
        conn: SQLite database connection.
        file_path: Migration SQL file.
    """
    filename = file_path.name
    
    logger.info(f"Applying migration: {filename}")
    
    sql = file_path.read_text(encoding="utf-8").strip()
    
    if not sql:
        raise RuntimeError(f"Migration file is empty: {filename}")
    
    try:
        # ----------------------------------------------------
        # Start transaction
        # ----------------------------------------------------
        conn.execute("BEGIN")
        
        # ----------------------------------------------------
        # Split SQL by statements to handle ALTER TABLE safely
        # ----------------------------------------------------
        statements = _split_sql_statements(sql)
        
        for statement in statements:
            statement = statement.strip()
            
            if not statement:
                continue
            
            # Check if this is an ALTER TABLE ADD COLUMN
            if _is_alter_table_add_column(statement):
                _handle_alter_table(conn, statement)
            else:
                conn.execute(statement)
        
        # ----------------------------------------------------
        # Record migration
        # ----------------------------------------------------
        conn.execute(
            """
            INSERT INTO schema_migrations (filename)
            VALUES (?)
            """,
            (filename,),
        )
        
        conn.commit()
        
        logger.info(f"Migration applied successfully: {filename}")
        
    except Exception as e:
        conn.rollback()
        logger.exception(f"Migration failed: {filename}: {e}")
        raise


def _split_sql_statements(sql: str) -> List[str]:
    """
    Split SQL script into individual statements.
    Handles semicolons in SQL.
    """
    statements = []
    current = []
    
    for line in sql.split("\n"):
        stripped = line.strip()
        
        # Skip comments
        if stripped.startswith("--"):
            continue
        
        current.append(line)
        
        # Check if statement ends with semicolon
        if stripped.endswith(";"):
            statement = "\n".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
    
    # Add remaining
    if current:
        statement = "\n".join(current).strip()
        if statement:
            statements.append(statement)
    
    return statements


def _is_alter_table_add_column(statement: str) -> bool:
    """Check if statement is ALTER TABLE ADD COLUMN."""
    upper = statement.upper()
    return (
        "ALTER TABLE" in upper
        and "ADD COLUMN" in upper
    )


def _handle_alter_table(
    conn: sqlite3.Connection,
    statement: str,
) -> None:
    """
    Handle ALTER TABLE ADD COLUMN safely.
    Checks if column exists before adding.
    """
    # Parse table name and column name from statement
    # Example: ALTER TABLE groups ADD COLUMN last_share_date TIMESTAMP
    
    parts = statement.split()
    
    try:
        table_index = parts.index("TABLE")
        table_name = parts[table_index + 1]
        
        column_index = parts.index("COLUMN")
        column_name = parts[column_index + 1]
        
        # Check if column exists
        if column_exists(conn, table_name, column_name):
            logger.info(
                f"Column already exists: {table_name}.{column_name}"
            )
            return
        
        # Execute ALTER TABLE
        conn.execute(statement)
        logger.info(
            f"Added column: {table_name}.{column_name}"
        )
        
    except (ValueError, IndexError) as e:
        # If parsing fails, try executing directly
        logger.warning(
            f"Could not parse ALTER TABLE statement: {e}"
        )
        conn.execute(statement)


# ============================================================
# RUN MIGRATIONS
# ============================================================

def run_migrations(
    db_path: str = None,
    migrations_dir: str = "migrations",
) -> bool:
    """
    Run all pending migrations.
    
    Args:
        db_path: SQLite database path.
        migrations_dir: Migration directory.
    
    Returns:
        True if successful, False if any migration fails.
    """
    if db_path is None:
        db_path = get_db_path()
    
    migrations_path = Path(migrations_dir)
    
    # Make sure database directory exists
    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Find migrations
    migration_files = get_migration_files(migrations_path)
    
    if not migration_files:
        logger.warning("No migration files found.")
        return True
    
    # Connect database
    logger.info(f"Using database: {db_file}")
    
    conn = sqlite3.connect(str(db_file))
    
    try:
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")
        
        # Create migration tracking table
        init_migrations_table(conn)
        
        # Get already applied migrations
        applied = get_applied_migrations(conn)
        
        # Find pending migrations
        pending = [
            file_path
            for file_path in migration_files
            if file_path.name not in applied
        ]
        
        if not pending:
            logger.info("Database is already up to date.")
            return True
        
        logger.info(f"Pending migrations: {len(pending)}")
        
        # Apply migrations in order
        for file_path in pending:
            logger.info(f"Running: {file_path.name}")
            
            try:
                apply_migration(conn, file_path)
            except Exception as exc:
                logger.error(
                    f"Stopping migration process because "
                    f"{file_path.name} failed: {exc}"
                )
                return False
        
        logger.info("All migrations completed successfully.")
        return True
        
    finally:
        conn.close()


# ============================================================
# CLI ENTRY POINT
# ============================================================

def main() -> None:
    """Command-line entry point."""
    setup_logging()
    
    logger.info("=" * 50)
    logger.info("AI Teacher Bot - Database Migration")
    logger.info("=" * 50)
    
    try:
        success = run_migrations()
        
        if not success:
            logger.error("Migration process failed.")
            sys.exit(1)
        
        logger.info("Migration process finished.")
        
    except KeyboardInterrupt:
        logger.warning("Migration cancelled by user.")
        sys.exit(130)
        
    except Exception as exc:
        logger.exception(f"Unexpected migration error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
