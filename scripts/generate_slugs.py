"""Generate slugs for all Inventory items that don't have one.

Idempotent — skips items that already have slugs.
Handles duplicates by appending -2, -3, etc.

Usage:
    flask shell < scripts/generate_slugs.py
    # or
    cd /opt/apps/infra && docker compose exec mouse-domination flask shell < scripts/generate_slugs.py
"""
import re
import sys

from app import create_app
from extensions import db
from models.business import Inventory

MAX_SLUG_LEN = 200


def slugify(name):
    """Convert product name to URL-safe slug."""
    if not name:
        return 'product'
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')
    return slug or 'product'


def generate_slugs(dry_run=False):
    """Generate unique slugs for all inventory items missing one."""
    items = Inventory.query.filter(Inventory.slug.is_(None)).all()

    if not items:
        print('All items already have slugs. Nothing to do.')
        return 0

    # Collect existing slugs to check uniqueness
    existing = {
        row.slug for row in db.session.query(Inventory.slug).filter(Inventory.slug.isnot(None)).all()
    }

    updated = 0
    for item in items:
        base_slug = slugify(item.product_name)[:MAX_SLUG_LEN]
        slug = base_slug
        counter = 1

        while slug in existing:
            counter += 1
            if counter > 10000:
                raise ValueError(f"Could not generate unique slug for '{item.product_name}'")
            suffix = f'-{counter}'
            slug = f'{base_slug[:MAX_SLUG_LEN - len(suffix)]}{suffix}'

        existing.add(slug)
        item.slug = slug
        updated += 1
        print(f'  [{item.id}] {item.product_name} -> {slug}')

    if dry_run:
        print(f'\nDry run: {updated} slugs would be generated. No changes saved.')
        db.session.rollback()
    else:
        try:
            db.session.commit()
            print(f'\nDone: {updated} slugs generated and saved.')
        except Exception as e:
            db.session.rollback()
            print(f'\nError saving slugs: {e}', file=sys.stderr)
            raise

    return updated


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        dry_run = '--dry-run' in sys.argv
        generate_slugs(dry_run=dry_run)
