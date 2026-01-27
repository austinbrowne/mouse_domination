---
status: completed
priority: p1
issue_id: "014"
tags: [code-review, data-integrity, error-handling, pr-youtube-title-filter]
dependencies: []
---

# Transaction Safety Violation in Exception Handler

## Problem Statement

The `post_tweet_now()` exception handler attempts `db.session.commit()` after catching an exception. If the exception is a database error, the session may be in an inconsistent state, causing the commit to fail or produce undefined behavior.

**Why it matters:** Could cause silent data corruption or application crashes, making debugging difficult.

## Findings

**Location:** `/Users/austin/Git_Repos/mouse_domination/routes/podcasts/tweets.py:305-310`

**Vulnerable Code:**
```python
except Exception as e:
    log_exception(e, 'Failed to post tweet manually')
    config.status = EpisodeTweetConfig.STATUS_FAILED
    config.error_message = str(e)  # Also leaks info - see todo 003
    config.retry_count += 1
    db.session.commit()  # PROBLEM: Session may be broken
```

**Scenarios:**
1. **SQLAlchemy Error:** If `post_to_twitter` triggers a DB error internally, the session is invalidated. The subsequent `commit()` will fail.
2. **IntegrityError:** If there's a constraint violation, the session needs rollback, not commit.
3. **Connection Error:** Database connection may be lost, making commit impossible.

## Proposed Solutions

### Solution A: Rollback First, Then Re-fetch (Recommended)

```python
except Exception as e:
    log_exception(e, 'Failed to post tweet manually')
    db.session.rollback()  # Clear any bad state

    # Re-fetch in clean session to update status
    config = EpisodeTweetConfig.query.filter_by(
        episode_id=episode_id,
        user_id=current_user.id
    ).first()
    if config:
        config.status = EpisodeTweetConfig.STATUS_FAILED
        config.error_message = str(e)[:500]  # Truncate
        config.retry_count += 1
        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()  # Give up on status update
```

**Pros:** Handles all error types correctly
**Cons:** Extra query, more verbose
**Effort:** Small
**Risk:** Low

### Solution B: Catch Specific Exceptions

```python
except SocialPostingError as e:
    # Known API error - session is fine
    config.status = EpisodeTweetConfig.STATUS_FAILED
    config.error_message = str(e)[:500]
    config.retry_count += 1
    db.session.commit()
except SQLAlchemyError as e:
    db.session.rollback()
    log_exception(e, 'Database error during tweet post')
    # Return error without trying to update status
except Exception as e:
    db.session.rollback()
    log_exception(e, 'Unexpected error during tweet post')
```

**Pros:** More specific handling per error type
**Cons:** More code, may miss edge cases
**Effort:** Medium
**Risk:** Low

## Recommended Action

**Implement Solution A** - Always rollback first in exception handler, then attempt status update in clean session state.

## Technical Details

**Affected Files:**
- `/Users/austin/Git_Repos/mouse_domination/routes/podcasts/tweets.py` (lines 305-310)

## Acceptance Criteria

- [ ] Exception handler calls `db.session.rollback()` before any modifications
- [ ] Status update is attempted in clean session state
- [ ] Failed status update doesn't crash the request
- [ ] User still receives appropriate error response
- [ ] Add test for database error during posting

## Work Log

| Date | Action | Outcome |
|------|--------|---------|
| 2026-01-27 | Identified during code review | Created todo |

## Resources

- Flask-SQLAlchemy session handling: https://flask-sqlalchemy.palletsprojects.com/en/3.0.x/contexts/
- SQLAlchemy session states: https://docs.sqlalchemy.org/en/14/orm/session_state_management.html
