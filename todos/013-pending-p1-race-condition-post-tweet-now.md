---
status: completed
priority: p1
issue_id: "013"
tags: [code-review, data-integrity, security, pr-youtube-title-filter]
dependencies: []
---

# Race Condition in Manual Tweet Posting

## Problem Statement

The `post_tweet_now()` route queries tweet config without row-level locking, then checks status and posts. Concurrent requests (double-click, rapid retry) could bypass the "already posted" check and post duplicate tweets.

**Why it matters:** Users could accidentally post duplicate tweets to their Twitter account, causing embarrassment and potential account issues.

## Findings

**Location:** `/Users/austin/Git_Repos/mouse_domination/routes/podcasts/tweets.py:209-227`

**Vulnerable Code:**
```python
# No locking - both requests can read status as pending
config = EpisodeTweetConfig.query.filter_by(
    episode_id=episode_id,
    user_id=current_user.id
).first()

# Check happens after query without holding lock
if config.status == EpisodeTweetConfig.STATUS_POSTED:
    # Already posted - but both requests pass this check
```

**Scenario:**
1. User clicks "Post Tweet Now" at T=0
2. Request A reads config.status = 'pending' at T=1ms
3. User double-clicks, Request B reads config.status = 'pending' at T=2ms
4. Request A posts tweet at T=100ms
5. Request B posts tweet at T=150ms (duplicate!)
6. Both requests update status to 'posted'

**Contrast:** The scheduler service correctly uses `with_for_update()` at line 155.

## Proposed Solutions

### Solution A: Add Row-Level Locking (Recommended)

```python
config = EpisodeTweetConfig.query.filter_by(
    episode_id=episode_id,
    user_id=current_user.id
).with_for_update().first()
```

**Pros:** Database-level guarantee, consistent with scheduler pattern
**Cons:** Holds lock during Twitter API call
**Effort:** Small (1 line change)
**Risk:** Low

### Solution B: Optimistic Locking with Version Check

Add version column and check during update.

**Pros:** No lock held during API call
**Cons:** More complex, requires schema change
**Effort:** Medium
**Risk:** Low

### Solution C: Frontend Debounce + Backend Lock

Disable button on click + Solution A.

**Pros:** Defense in depth
**Cons:** Frontend-only is not sufficient
**Effort:** Small
**Risk:** Low

## Recommended Action

**Implement Solution A** - Add `with_for_update()` to the query. This is a 1-line fix that matches the existing pattern in the scheduler.

## Technical Details

**Affected Files:**
- `/Users/austin/Git_Repos/mouse_domination/routes/podcasts/tweets.py` (line 209)

## Acceptance Criteria

- [ ] `post_tweet_now()` uses `with_for_update()` when querying config
- [ ] Concurrent requests result in only one tweet posted
- [ ] Second request receives "already posted" error
- [ ] Existing tests pass
- [ ] Add test for concurrent posting scenario

## Work Log

| Date | Action | Outcome |
|------|--------|---------|
| 2026-01-27 | Identified during code review | Created todo |

## Resources

- Similar fix: `services/tweet_scheduler.py:155` uses `with_for_update()`
- SQLAlchemy docs: https://docs.sqlalchemy.org/en/14/orm/query.html#sqlalchemy.orm.Query.with_for_update
