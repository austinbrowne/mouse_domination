"""Add database indexes for better query performance.

Run with: python -m scripts.add_indexes
"""
from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    # These use IF NOT EXISTS so safe to run multiple times
    db.session.execute(text('CREATE INDEX IF NOT EXISTS ix_inventory_status ON inventory(status)'))
    db.session.execute(text('CREATE INDEX IF NOT EXISTS ix_inventory_sold ON inventory(sold)'))
    db.session.execute(text('CREATE INDEX IF NOT EXISTS ix_inventory_created_at ON inventory(created_at)'))
    db.session.commit()
    print("Indexes created successfully")
