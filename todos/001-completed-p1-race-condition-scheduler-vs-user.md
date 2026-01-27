---
status: completed
priority: p1
issue_id: "001"
tags: [code-review, data-integrity, scheduler, pr-22]
dependencies: []
---

# Race Condition: Scheduler Posts Tweet After User Disables

## Problem Statement

The background scheduler reads tweet config status and posts tweets without holding a lock. A user could disable their tweet config via the UI between when the scheduler reads the config and when it posts.

**Why it matters:** Users who explicitly disabled their tweet automation may still have tweets posted on their behalf, violating user intent and potentially damaging trust.

## Findings

**Location:** `/Users/austin/Git_Repos/mouse_domination/services/tweet_scheduler.py:169-262`

**Scenario:**
1. Scheduler reads `tweet_config.status = 'pending'` at T=0
2. User sets `tweet_config.enabled = False` via UI at T=1ms
3. User commits at T=2ms
4. Scheduler posts tweet at T=5ms (based on stale data)
5. Scheduler commits `status = 'posted'` at T=6ms
6. Result: Tweet posted despite user disabling it

**Root cause:** No optimistic locking or `SELECT FOR UPDATE` when reading configs for posting.

## Proposed Solutions

### Solution A: SELECT FOR UPDATE (Recommended)
Add row-level locking when reading configs for posting.

```python
config = EpisodeTweetConfig.query.with_for_update().filter_by(
    id=tweet_config.id,
    status=EpisodeTweetConfig.STATUS_PENDING,
    enabled=True
).first()
if not config:
    return False  # Config was modified
```

**Pros:** Database-level guarantee, simple to implement
**Cons:** Holds lock during HTTP calls to Twitter (could be slow)
**Effort:** Small
**Risk:** Low

### Solution B: Optimistic Locking with Version Column
Add a version column that increments on each update, check version before committing.

```python
# In model
version = db.Column(db.Integer, nullable=False, server_default='1')

# Before posting
original_version = config.version
# ... post tweet ...
if config.version != original_version:
    db.session.rollback()
    return False
```

**Pros:** No long-held locks
**Cons:** More complex, requires schema change
**Effort:** Medium
**Risk:** Low

### Solution C: Re-read Before Commit
Simple re-read of enabled status before final commit.

```python
# After posting, before commit
db.session.refresh(config)
if not config.enabled:
    db.session.rollback()
    return False
```

**Pros:** Simple, no schema change
**Cons:** Still a small race window
**Effort:** Small
**Risk:** Medium (doesn't fully eliminate race)

## Recommended Action

<!-- To be filled during triage -->

## Technical Details

**Affected files:**
- `services/tweet_scheduler.py` - `_post_tweet_for_host()` method

**Database changes:** None for Solution A or C; Solution B requires migration

## Acceptance Criteria

- [ ] User disabling tweet config prevents scheduler from posting
- [ ] No tweets posted for disabled configs under any race condition
- [ ] Test case covering concurrent disable + post scenario

## Work Log

| Date | Action | Result/Learning |
|------|--------|-----------------|
| 2026-01-25 | Identified during code review | Found via data-integrity-guardian agent |

## Resources

- PR #22: Add automated tweet scheduling
- Similar pattern: Optimistic locking in SQLAlchemy docs
