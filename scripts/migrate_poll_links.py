#!/usr/bin/env python3
"""
Migration script to add poll link fields to episode_guides table.

Run with: python scripts/migrate_poll_links.py
"""
import sqlite3
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

DB_PATH = Path(__file__).parent.parent / 'mouse_domination.db'


def migrate():
    """Add previous_poll_link and new_poll_link columns to episode_guides table."""
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        print("Run the app first to create the database.")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check existing columns
        cursor.execute("PRAGMA table_info(episode_guides)")
        columns = {row[1] for row in cursor.fetchall()}

        migrations_run = 0

        # Add previous_poll_link if missing
        if 'previous_poll_link' not in columns:
            print("Adding previous_poll_link column...")
            cursor.execute("""
                ALTER TABLE episode_guides
                ADD COLUMN previous_poll_link VARCHAR(500)
            """)
            migrations_run += 1
            print("  Done.")
        else:
            print("previous_poll_link column already exists.")

        # Add new_poll_link if missing
        if 'new_poll_link' not in columns:
            print("Adding new_poll_link column...")
            cursor.execute("""
                ALTER TABLE episode_guides
                ADD COLUMN new_poll_link VARCHAR(500)
            """)
            migrations_run += 1
            print("  Done.")
        else:
            print("new_poll_link column already exists.")

        conn.commit()
        print(f"\nMigration complete. {migrations_run} column(s) added.")
        return True

    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == '__main__':
    success = migrate()
    sys.exit(0 if success else 1)
