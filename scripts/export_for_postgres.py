#!/usr/bin/env python3
"""Export SQLite data to PostgreSQL-compatible SQL file."""

import sqlite3
import os
from datetime import datetime

# Path to your SQLite database
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'mouse_domination.db')
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), 'data_export.sql')

# Tables in dependency order (referenced tables first)
TABLES = [
    'users',
    'companies',
    'contacts',
    'inventory',
    'affiliate_revenue',
    'collaborations',
    'sales_pipeline',
    'outreach_templates',
    'custom_options',
    'episode_guide_templates',
    'episode_guides',
    'episode_guide_items',
    'creator_profiles',
    'rate_cards',
    'testimonials',
    'discord_integrations',
    'discord_emoji_mappings',
    'discord_import_logs',
]


def escape_value(val, col_name=None):
    """Escape a value for PostgreSQL."""
    # Boolean columns in the schema (from SQLAlchemy models)
    BOOLEAN_COLUMNS = {
        'discussed', 'follow_up_needed', 'is_active', 'is_admin',
        'is_approved', 'is_default', 'is_negotiable', 'is_public',
        'on_amazon', 'sold'
    }

    if val is None:
        return 'NULL'
    elif isinstance(val, bool):
        return 'TRUE' if val else 'FALSE'
    elif isinstance(val, int):
        # Check if this is a boolean column stored as 0/1
        if col_name and col_name.lower() in BOOLEAN_COLUMNS:
            return 'TRUE' if val else 'FALSE'
        return str(val)
    elif isinstance(val, float):
        return str(val)
    elif isinstance(val, str):
        # Escape single quotes and backslashes
        escaped = val.replace("'", "''").replace("\\", "\\\\")
        return f"'{escaped}'"
    elif isinstance(val, bytes):
        # Handle binary data
        return f"'\\x{val.hex()}'"
    else:
        escaped = str(val).replace("'", "''")
        return f"'{escaped}'"


def get_table_columns(cursor, table):
    """Get column names for a table."""
    cursor.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cursor.fetchall()]


def export_table(cursor, table, outfile):
    """Export a single table to SQL INSERT statements."""
    columns = get_table_columns(cursor, table)

    cursor.execute(f"SELECT * FROM {table}")
    rows = cursor.fetchall()

    if not rows:
        outfile.write(f"-- Table {table}: no data\n\n")
        return 0

    outfile.write(f"-- Table: {table} ({len(rows)} rows)\n")

    for row in rows:
        values = [escape_value(val, col) for val, col in zip(row, columns)]
        cols_str = ', '.join(columns)
        vals_str = ', '.join(values)
        outfile.write(f"INSERT INTO {table} ({cols_str}) VALUES ({vals_str});\n")

    outfile.write("\n")
    return len(rows)


def reset_sequences(cursor, outfile):
    """Generate commands to reset PostgreSQL sequences after import."""
    outfile.write("-- Reset sequences to max ID + 1\n")

    for table in TABLES:
        # Check if table has an 'id' column
        columns = get_table_columns(cursor, table)
        if 'id' in columns:
            cursor.execute(f"SELECT MAX(id) FROM {table}")
            max_id = cursor.fetchone()[0]
            if max_id:
                outfile.write(f"SELECT setval('{table}_id_seq', {max_id}, true);\n")

    outfile.write("\n")


def main():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    with open(OUTPUT_PATH, 'w') as outfile:
        outfile.write("-- PostgreSQL data export from SQLite\n")
        outfile.write(f"-- Generated: {datetime.now().isoformat()}\n")
        outfile.write("-- Run this AFTER the Flask app has created the tables\n\n")

        outfile.write("BEGIN;\n\n")

        # Disable foreign key checks during import
        outfile.write("SET session_replication_role = 'replica';\n\n")

        total_rows = 0
        for table in TABLES:
            try:
                rows = export_table(cursor, table, outfile)
                total_rows += rows
                print(f"  {table}: {rows} rows")
            except sqlite3.OperationalError as e:
                print(f"  {table}: skipped ({e})")
                outfile.write(f"-- Table {table}: skipped ({e})\n\n")

        # Re-enable foreign key checks
        outfile.write("SET session_replication_role = 'origin';\n\n")

        # Reset sequences
        reset_sequences(cursor, outfile)

        outfile.write("COMMIT;\n")

    conn.close()

    print(f"\nExported {total_rows} total rows to {OUTPUT_PATH}")
    print(f"\nNext steps:")
    print(f"  1. Copy to server: scp {OUTPUT_PATH} austin@178.156.211.75:/tmp/")
    print(f"  2. Import: docker compose exec -T postgres psql -U mousedom -d mousedom < /tmp/data_export.sql")


if __name__ == '__main__':
    main()
