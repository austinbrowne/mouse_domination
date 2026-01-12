#!/usr/bin/env python3
"""Migration script to add multi-user support.

Creates users table and assigns all existing inventory to Austin.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone
from app import create_app, db
from models import User, Inventory

AUSTIN_EMAIL = 'austinjbrowne@gmail.com'


def migrate():
    app = create_app()
    with app.app_context():
        # Check if users table exists
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()

        if 'users' not in tables:
            print("Creating users table...")
            # Create just the users table
            User.__table__.create(db.engine)
            print("Users table created.")
        else:
            print("Users table already exists.")

        # Check if user_id column exists in inventory
        columns = [col['name'] for col in inspector.get_columns('inventory')]

        if 'user_id' not in columns:
            print("Adding user_id column to inventory...")
            # SQLite doesn't support adding NOT NULL columns directly
            # Add as nullable first
            db.session.execute(db.text('ALTER TABLE inventory ADD COLUMN user_id INTEGER REFERENCES users(id)'))
            db.session.commit()
            print("user_id column added.")
        else:
            print("user_id column already exists.")

        # Create Austin's user if not exists
        austin = User.query.filter_by(email=AUSTIN_EMAIL).first()
        if not austin:
            print(f"Creating user for {AUSTIN_EMAIL}...")
            austin = User(email=AUSTIN_EMAIL, created_at=datetime.now(timezone.utc))
            db.session.add(austin)
            db.session.commit()
            print(f"User created with ID {austin.id}.")
        else:
            print(f"User {AUSTIN_EMAIL} already exists with ID {austin.id}.")

        # Assign all unassigned inventory to Austin
        unassigned_count = Inventory.query.filter(Inventory.user_id.is_(None)).count()
        if unassigned_count > 0:
            print(f"Assigning {unassigned_count} inventory items to Austin...")
            Inventory.query.filter(Inventory.user_id.is_(None)).update({Inventory.user_id: austin.id})
            db.session.commit()
            print(f"Assigned {unassigned_count} items to Austin.")
        else:
            print("All inventory items already have a user assigned.")

        # Create index on user_id if it doesn't exist
        indexes = [idx['name'] for idx in inspector.get_indexes('inventory')]
        if 'ix_inventory_user_id' not in indexes:
            print("Creating index on inventory.user_id...")
            db.session.execute(db.text('CREATE INDEX ix_inventory_user_id ON inventory (user_id)'))
            db.session.commit()
            print("Index created.")

        # Verify
        total_inventory = Inventory.query.count()
        austin_inventory = Inventory.query.filter_by(user_id=austin.id).count()
        print(f"\nMigration complete!")
        print(f"Total inventory items: {total_inventory}")
        print(f"Items assigned to Austin: {austin_inventory}")


if __name__ == '__main__':
    migrate()
