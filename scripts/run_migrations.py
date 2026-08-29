"""
AI Teacher Bot - Database Migration Runner

Usage:
    python scripts/run_migrations.py

This script:
- Finds SQL migration files in migrations/
- Runs migrations in filename order
- Tracks completed migrations
- Safely handles ALTER TABLE ADD COLUMN
- Rolls back a failed migration
"""

import logging
import sqlite3
import sys
from pathlib import Path
from typing import List, Set


# ============================================================
# PATHS
# ============================================================

# Project root:
# ai_teacher_bot/
# ├── scripts/
# │   └── run_migrations.py
# ├── migrations/
# └── data/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

MIGRATIONS_DIR = PROJECT_ROOT / "migrations"


# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger("migration")


def setup_logging() -> None:
    """Setup console logging."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )


# ============================================================
# DATABASE CONFIG
# ============================================================

def get_db_path() -> Path:
    """
    Get SQLite database path.

    Uses config.py when available.
    Falls back to data/app.db.
    """

    try:
        sys.path.insert(0, str(PROJECT_ROOT))

        from config import get_config

        config = get_config()
        return PROJECT_ROOT / config.sqlite_db_path

    except Exception as exc:
        logger.warning(
            f"Could not load database path from config: {exc}"
        )

        return PROJECT_ROOT / "data" / "app.db"


# ============================================================
# MIGRATION FILES
# ============================================================

def get_migration_files(
    migrations_dir: Path,
) -> List[Path]:
    """Return all SQL migration files sorted by filename."""

    if not migrations_dir.exists():
        logger.error(
            f"Migrations directory not found: {migrations_dir}"
        )
        return []

    files = sorted(
        migrations_dir.glob("*.sql")
    )

    logger.info(
        f"Found {len(files)} migration file(s)."
    )

    return files


# ============================================================
# MIGRATION TRACKING
# ============================================================

def init_migrations_table(
    conn: sqlite3.Connection,
) -> None:
    """Create schema_migrations table."""

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


def get_applied_migrations(
    conn: sqlite3.Connection,
) -> Set[str]:
    """Return names of already-applied migrations."""

    cursor = conn.execute(
        """
        SELECT filename
        FROM schema_migrations
        ORDER BY id
        """
    )

    rows = cursor.fetchall()

    return {
        row[0]
        for row in rows
    }


# ============================================================
# SQL HELPERS
# ============================================================

def split_sql_statements(
    sql: str,
) -> List[str]:
    """
    Split a simple SQL migration file into statements.

    This project uses normal SQLite migration statements,
    so semicolon-based splitting is sufficient.
    """

    statements = []

    for statement in sql.split(";"):
        statement = statement.strip()

        if not statement:
            continue

        # Remove full-line comments.
        lines = []

        for line in statement.splitlines():

            stripped = line.strip()

            if stripped.startswith("--"):
                continue

            lines.append(line)

        cleaned = "\n".join(lines).strip()

        if cleaned:
            statements.append(cleaned)

    return statements


def column_exists(
    conn: sqlite3.Connection,
    table: str,
    column: str,
) -> bool:
    """Check whether a column already exists."""

    cursor = conn.execute(
        f"PRAGMA table_info({table})"
    )

    columns = cursor.fetchall()

    return any(
        row[1] == column
        for row in columns
    )


def is_add_column_statement(
    statement: str,
) -> bool:
    """Check whether SQL is ALTER TABLE ... ADD COLUMN."""

    normalized = " ".join(
        statement.upper().split()
    )

    return (
        normalized.startswith("ALTER TABLE ")
        and " ADD COLUMN " in normalized
    )


def handle_add_column(
    conn: sqlite3.Connection,
    statement: str,
) -> None:
    """
    Safely execute ALTER TABLE ADD COLUMN.

    If the column already exists, skip it.
    """

    parts = statement.split()

    upper_parts = [
        part.upper()
        for part in parts
    ]

    try:
        table_index = upper_parts.index("TABLE")
        column_index = upper_parts.index("COLUMN")

        table_name = parts[table_index + 1]
        column_name = parts[column_index + 1]

        # Remove possible comma.
        column_name = column_name.rstrip(",")

        if column_exists(
            conn,
            table_name,
            column_name,
        ):
            logger.info(
                f"Column already exists: "
                f"{table_name}.{column_name}"
            )
            return

        conn.execute(statement)

        logger.info(
            f"Added column: "
            f"{table_name}.{column_name}"
        )

    except (ValueError, IndexError):

        logger.warning(
            "Could not parse ALTER TABLE statement. "
            "Executing directly."
        )

        conn.execute(statement)


# ============================================================
# APPLY MIGRATION
# ============================================================

def apply_migration(
    conn: sqlite3.Connection,
    file_path: Path,
) -> bool:
    """
    Apply one migration.

    If anything fails:
    - rollback changes
    - migration is not recorded
    """

    filename = file_path.name

    logger.info(
        f"Applying migration: {filename}"
    )

    try:
        sql = file_path.read_text(
            encoding="utf-8"
        ).strip()

        if not sql:
            raise ValueError(
                f"Migration file is empty: {filename}"
            )

        statements = split_sql_statements(sql)

        if not statements:
            raise ValueError(
                f"No SQL statements found: {filename}"
            )

        # Start transaction.
        conn.execute("BEGIN")

        for statement in statements:

            if is_add_column_statement(statement):

                handle_add_column(
                    conn,
                    statement,
                )

            else:

                conn.execute(statement)

        # Record successful migration.
        conn.execute(
            """
            INSERT INTO schema_migrations
                (filename)
            VALUES
                (?)
            """,
            (filename,),
        )

        conn.commit()

        logger.info(
            f"✅ Applied: {filename}"
        )

        return True

    except Exception as exc:

        conn.rollback()

        logger.error(
            f"❌ Failed: {filename}"
        )

        logger.error(
            f"Reason: {exc}"
        )

        return False


# ============================================================
# RUN MIGRATIONS
# ============================================================

def run_migrations(
    db_path: Path | None = None,
    migrations_dir: Path | None = None,
) -> bool:
    """Run all pending migrations in order."""

    if db_path is None:
        db_path = get_db_path()

    if migrations_dir is None:
        migrations_dir = MIGRATIONS_DIR

    # Create database directory.
    db_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    migration_files = get_migration_files(
        migrations_dir
    )

    if not migration_files:
        logger.warning(
            "No migration files found."
        )
        return True

    logger.info(
        f"Database: {db_path}"
    )

    conn = sqlite3.connect(
        str(db_path)
    )

    try:

        # Enable foreign keys.
        conn.execute(
            "PRAGMA foreign_keys = ON"
        )

        # Create migration tracking table.
        init_migrations_table(conn)

        applied = get_applied_migrations(
            conn
        )

        pending = [
            file
            for file in migration_files
            if file.name not in applied
        ]

        if not pending:

            logger.info(
                "Database is already up to date."
            )

            return True

        logger.info(
            f"Pending migrations: "
            f"{len(pending)}"
        )

        # Run migrations in order.
        for migration in pending:

            success = apply_migration(
                conn,
                migration,
            )

            if not success:

                logger.error(
                    "🛑 Migration process stopped."
                )

                logger.error(
                    f"Failed migration: "
                    f"{migration.name}"
                )

                return False

        logger.info(
            "=" * 50
        )

        logger.info(
            "✅ All migrations completed successfully."
        )

        logger.info(
            "=" * 50
        )

        return True

    finally:

        conn.close()


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    """CLI entry point."""

    setup_logging()

    logger.info(
        "=" * 50
    )

    logger.info(
        "AI Teacher Bot - Database Migration"
    )

    logger.info(
        "=" * 50
    )

    try:

        success = run_migrations()

        if not success:

            logger.error(
                "❌ Migration process failed."
            )

            sys.exit(1)

        logger.info(
            "Migration process finished."
        )

    except KeyboardInterrupt:

        logger.warning(
            "Migration cancelled by user."
        )

        sys.exit(130)

    except Exception as exc:

        logger.exception(
            f"Unexpected migration error: {exc}"
        )

        sys.exit(1)


if __name__ == "__main__":
    main()
