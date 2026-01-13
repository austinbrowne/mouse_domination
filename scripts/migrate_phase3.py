#!/usr/bin/env python3
"""
Migration script for Phase 3 - Episode Guide Templates and Custom Sections.

Run this on production after deploying the new code:
    python scripts/migrate_phase3.py

This adds:
- episode_guide_templates table
- template_id, intro_static_content, outro_static_content, custom_sections columns to episode_guides
"""

import sqlite3
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_db_path():
    """Get database path from environment or default."""
    return os.environ.get('DATABASE_PATH', 'mouse_domination.db')

def migrate():
    db_path = get_db_path()
    print(f"Migrating database: {db_path}")

    if not os.path.exists(db_path):
        print(f"ERROR: Database file not found: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create episode_guide_templates table
    print("Creating episode_guide_templates table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS episode_guide_templates (
            id INTEGER PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            intro_static_content TEXT,
            outro_static_content TEXT,
            default_sections TEXT,
            default_poll_1 VARCHAR(200),
            default_poll_2 VARCHAR(200),
            created_by INTEGER REFERENCES users(id),
            created_at DATETIME,
            updated_at DATETIME,
            is_default BOOLEAN DEFAULT 0
        )
    ''')

    # Create index on template name
    try:
        cursor.execute('CREATE INDEX IF NOT EXISTS ix_episode_guide_templates_name ON episode_guide_templates(name)')
    except:
        pass

    # Add new columns to episode_guides
    columns_to_add = [
        ('template_id', 'INTEGER REFERENCES episode_guide_templates(id)'),
        ('intro_static_content', 'TEXT'),
        ('outro_static_content', 'TEXT'),
        ('custom_sections', 'TEXT'),
    ]

    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f'ALTER TABLE episode_guides ADD COLUMN {col_name} {col_type}')
            print(f"  Added column: {col_name}")
        except sqlite3.OperationalError as e:
            if 'duplicate column' in str(e).lower():
                print(f"  Column already exists: {col_name}")
            else:
                print(f"  Error adding {col_name}: {e}")

    conn.commit()
    conn.close()

    print("\nMigration complete!")
    print("\nRestart the application to apply changes.")

if __name__ == '__main__':
    migrate()
