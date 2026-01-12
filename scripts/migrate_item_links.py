#!/usr/bin/env python3
"""Migration script to add multiple links support to episode_guide_items.

Adds 'links' JSON column and migrates existing single 'link' values.
"""
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db


def migrate():
    app = create_app()
    with app.app_context():
        inspector = db.inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('episode_guide_items')]

        # Add links column if it doesn't exist
        if 'links' not in columns:
            print("Adding 'links' column to episode_guide_items...")
            # Use TEXT type for SQLite (JSON is stored as TEXT anyway)
            db.session.execute(db.text('ALTER TABLE episode_guide_items ADD COLUMN links TEXT'))
            db.session.commit()
            print("  Done.")
        else:
            print("'links' column already exists.")

        # Migrate existing single link values to links array
        print("Migrating existing link data...")
        result = db.session.execute(db.text(
            "SELECT id, link FROM episode_guide_items WHERE link IS NOT NULL AND link != '' AND links IS NULL"
        ))
        items = result.fetchall()

        migrated = 0
        for item_id, link in items:
            links_json = json.dumps([link])
            db.session.execute(
                db.text("UPDATE episode_guide_items SET links = :links WHERE id = :id"),
                {'links': links_json, 'id': item_id}
            )
            migrated += 1

        db.session.commit()
        print(f"  Migrated {migrated} items with existing links.")

        print("\nMigration complete!")


if __name__ == '__main__':
    migrate()
