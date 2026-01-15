#!/usr/bin/env python3
"""Check and fix episode guide item positions."""

from app import create_app
from models import db, EpisodeGuideItem
from sqlalchemy import func

app = create_app()

def check_positions():
    """Check for position issues in episode guide items."""
    with app.app_context():
        items = EpisodeGuideItem.query.order_by(
            EpisodeGuideItem.guide_id,
            EpisodeGuideItem.section,
            EpisodeGuideItem.position
        ).all()

        issues = []
        current_guide = None
        current_section = None
        expected_pos = 0

        for item in items:
            if item.guide_id != current_guide or item.section != current_section:
                current_guide = item.guide_id
                current_section = item.section
                expected_pos = 0

            if item.position != expected_pos:
                issues.append({
                    'guide_id': item.guide_id,
                    'section': item.section,
                    'item_id': item.id,
                    'current_pos': item.position,
                    'expected_pos': expected_pos
                })
            expected_pos += 1

        return issues


def fix_positions():
    """Normalize all positions to 0, 1, 2, ... per section."""
    with app.app_context():
        # Get all guide/section combinations
        combos = db.session.query(
            EpisodeGuideItem.guide_id,
            EpisodeGuideItem.section
        ).distinct().all()

        fixed_count = 0
        for guide_id, section in combos:
            items = EpisodeGuideItem.query.filter_by(
                guide_id=guide_id,
                section=section
            ).order_by(EpisodeGuideItem.position).all()

            for i, item in enumerate(items):
                if item.position != i:
                    item.position = i
                    fixed_count += 1

        db.session.commit()
        return fixed_count


if __name__ == '__main__':
    import sys

    if '--fix' in sys.argv:
        print('Fixing positions...')
        count = fix_positions()
        print(f'Fixed {count} position(s)')
    else:
        issues = check_positions()
        if issues:
            print(f'Found {len(issues)} position issues:')
            for issue in issues[:20]:
                print(f"  Guide {issue['guide_id']}, Section {issue['section']}: "
                      f"Item {issue['item_id']} has pos {issue['current_pos']}, expected {issue['expected_pos']}")
            if len(issues) > 20:
                print(f'  ... and {len(issues) - 20} more')
            print('\nRun with --fix to normalize positions')
        else:
            print('No position issues found - all positions are normalized (0, 1, 2, ...)')
