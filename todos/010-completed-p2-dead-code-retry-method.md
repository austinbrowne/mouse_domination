---
status: completed
priority: p2
issue_id: "010"
tags: [code-review, simplification, dead-code, pr-22]
dependencies: []
---

# Dead Code: retry_failed_tweets() Never Called

## Problem Statement

The `retry_failed_tweets()` method is defined but never called anywhere in the codebase. No scheduled job invokes it, no route calls it.

**Why it matters:** Dead code increases maintenance burden and confuses readers about system behavior.

## Findings

**Location:** `/Users/austin/Git_Repos/mouse_domination/services/tweet_scheduler.py:364-386`

```python
def retry_failed_tweets(self, max_retries: int = 3):
    """
    Retry posting tweets that previously failed.
    ...
    """
    # 23 lines of code
```

**Verification:** Searched entire codebase - no calls to `retry_failed_tweets`.

**Related dead code found:**
- `services/scheduler.py:166-173` - `get_scheduler()` and `is_scheduler_running()` unused
- `services/youtube_live.py:194-196` - `get_video_url()` unused
- `models/podcast.py:125` - `STATUS_DISABLED` constant unused

## Proposed Solutions

### Solution A: Remove Dead Code (Recommended if retry not needed)

Delete the unused methods and constant:
- `retry_failed_tweets()` - 23 lines
- `get_scheduler()` - 3 lines
- `is_scheduler_running()` - 3 lines
- `get_video_url()` - 3 lines
- `STATUS_DISABLED` - 1 line

**Total: 33 lines removed**

**Pros:** Cleaner codebase, less confusion
**Cons:** Need to re-implement if retry is wanted later
**Effort:** Trivial
**Risk:** None

### Solution B: Wire Up Retry Logic (if retry is needed)

Add a scheduled job that calls `retry_failed_tweets()`:

```python
scheduler.add_job(
    func=_job_retry_failed_tweets,
    trigger='interval',
    hours=1,
    id='retry_failed_tweets',
    ...
)
```

**Pros:** Complete the half-built feature
**Cons:** More complexity
**Effort:** Small
**Risk:** Low

## Recommended Action

<!-- To be filled during triage - decide if retry is needed -->

## Technical Details

**Affected files:**
- `services/tweet_scheduler.py`
- `services/scheduler.py`
- `services/youtube_live.py`
- `models/podcast.py`

## Acceptance Criteria

- [ ] Decision made: remove or wire up retry
- [ ] If removing: all dead code deleted
- [ ] If keeping: retry job scheduled and tested

## Work Log

| Date | Action | Result/Learning |
|------|--------|-----------------|
| 2026-01-25 | Identified during simplicity review | code-simplicity-reviewer agent |

## Resources

- PR #22: Add automated tweet scheduling
