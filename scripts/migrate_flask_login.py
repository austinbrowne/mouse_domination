#!/usr/bin/env python3
"""Migration script for Flask-Login authentication.

Adds authentication columns to users table and sets up Austin as admin.
"""
import sys
import os
import getpass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from models import User

AUSTIN_EMAIL = 'austinjbrowne@gmail.com'


def validate_password(password: str) -> list[str]:
    """Validate password strength."""
    errors = []
    if len(password) < 12:
        errors.append('Password must be at least 12 characters')
    if not any(c.isupper() for c in password):
        errors.append('Must contain uppercase letter')
    if not any(c.islower() for c in password):
        errors.append('Must contain lowercase letter')
    if not any(c.isdigit() for c in password):
        errors.append('Must contain digit')
    if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password):
        errors.append('Must contain special character')
    return errors


def migrate():
    app = create_app()
    with app.app_context():
        inspector = db.inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('users')]

        # Add new columns if they don't exist
        new_columns = [
            ('password_hash', 'VARCHAR(255)'),
            ('failed_login_attempts', 'INTEGER DEFAULT 0'),
            ('locked_until', 'DATETIME'),
            ('password_changed_at', 'DATETIME'),
            ('is_approved', 'BOOLEAN DEFAULT 0'),
            ('is_admin', 'BOOLEAN DEFAULT 0'),
        ]

        for col_name, col_type in new_columns:
            if col_name not in columns:
                print(f"Adding column {col_name}...")
                db.session.execute(db.text(f'ALTER TABLE users ADD COLUMN {col_name} {col_type}'))
                db.session.commit()

        print("Database schema updated.")

        # Find or create Austin's user
        austin = User.query.filter_by(email=AUSTIN_EMAIL).first()
        if not austin:
            print(f"User {AUSTIN_EMAIL} not found!")
            return

        print(f"\nSetting up admin account for {AUSTIN_EMAIL}")

        # Get password
        while True:
            password = getpass.getpass("Enter new password (min 12 chars, upper/lower/digit/special): ")
            errors = validate_password(password)
            if errors:
                for e in errors:
                    print(f"  - {e}")
                continue

            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                print("Passwords don't match. Try again.")
                continue

            break

        # Set password and admin status
        austin.set_password(password)
        austin.is_approved = True
        austin.is_admin = True
        db.session.commit()

        print(f"\nSuccess! {AUSTIN_EMAIL} is now an admin with password set.")
        print("\nYou can now log in at /auth/login")


if __name__ == '__main__':
    migrate()
