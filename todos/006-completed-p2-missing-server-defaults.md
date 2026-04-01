---
status: completed
priority: p2
issue_id: "006"
tags: [code-review, data-integrity, migration, pr-22]
dependencies: []
---

# Missing server_default for Critical Columns in Migration

## Problem Statement

The migration uses SQLAlchemy `default=` for boolean and integer columns, which only applies when using the ORM. Direct SQL inserts or database recovery would have NULL values.

**Why it matters:** If `status` becomes NULL, tweets are silently excluded from scheduler queries - effectively "lost" and never posted.

## Findings

**Location:** `/Users/austin/Git_Repos/mouse_domination/migrations/versions/h9i0j1k2l3m4_add_twitter_scheduling.py:33-40`

```python
sa.Column('enabled', sa.Boolean(), default=True),           # ORM-only
sa.Column('include_url', sa.Boolean(), default=True),       # ORM-only
sa.Column('status', sa.String(length=20), default='pending'),  # ORM-only, also allows NULL
sa.Column('retry_count', sa.Integer(), default=0),          # ORM-only
```

**Risk scenario:** Direct SQL insert or data recovery operation would leave these columns NULL.

## Proposed Solutions

### Solution A: New Migration with server_default (Recommended)

Create a new migration to add proper defaults:

```python
def upgrade():
    with op.batch_alter_table('episode_tweet_configs', schema=None) as batch_op:
        batch_op.alter_column('enabled',
            existing_type=sa.Boolean(),
            server_default=sa.text('true'),
            nullable=False)
        batch_op.alter_column('include_url',
            existing_type=sa.Boolean(),
            server_default=sa.text('true'),
            nullable=False)
        batch_op.alter_column('status',
            existing_type=sa.String(length=20),
            server_default='pending',
            nullable=False)
        batch_op.alter_column('retry_count',
            existing_type=sa.Integer(),
            server_default='0',
            nullable=False)
```

**Pros:** Database-level protection, works for all insert methods
**Cons:** Requires migration
**Effort:** Small
**Risk:** Low (additive change)

## Recommended Action

<!-- To be filled during triage -->

## Technical Details

**Affected files:**
- New migration file needed

**Current migration:** `migrations/versions/h9i0j1k2l3m4_add_twitter_scheduling.py`

## Acceptance Criteria

- [ ] All four columns have `server_default`
- [ ] All four columns are `nullable=False`
- [ ] Migration runs cleanly on existing data
- [ ] Direct SQL insert works without specifying these columns

## Work Log

| Date | Action | Result/Learning |
|------|--------|-----------------|
| 2026-01-25 | Identified during data integrity review | data-integrity-guardian agent |

## Resources

- PR #22: Add automated tweet scheduling
- SQLAlchemy server_default: https://docs.sqlalchemy.org/en/20/core/defaults.html
