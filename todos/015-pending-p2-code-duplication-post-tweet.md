---
status: completed
priority: p2
issue_id: "015"
tags: [code-review, architecture, dry, pr-youtube-title-filter]
dependencies: ["013", "014"]
---

# Code Duplication: post_tweet_now Duplicates Service Logic

## Problem Statement

The `post_tweet_now()` route handler duplicates ~40 lines of logic from `TweetSchedulerService._post_tweet_for_host()`. This violates DRY and creates a maintenance burden where changes must be made in two places.

**Why it matters:** Future changes to tweet posting logic may be applied to one location but not the other, causing inconsistent behavior.

## Findings

**Duplicated blocks:**

| Logic | Route Location | Service Location |
|-------|----------------|------------------|
| Content fallback (custom → generated → title) | tweets.py:244-248 | tweet_scheduler.py:231-236 |
| Twitter API call + result handling | tweets.py:263-287 | tweet_scheduler.py:250-277 |
| Status update on success | tweets.py:266-270 | tweet_scheduler.py:254-258 |
| SocialPostLog creation | tweets.py:273-283 | tweet_scheduler.py:261-271 |
| Status update on failure | tweets.py:295-298 | tweet_scheduler.py:279-282 |

**Total duplication:** ~40 lines with ~85-90% similarity

## Proposed Solutions

### Solution A: Extract Shared Method in Service (Recommended)

Create `TweetSchedulerService.post_tweet_for_user()` that both the scheduler and route can call:

```python
# In TweetSchedulerService
def post_tweet_for_user(
    self, user_id: int, episode_id: int, connection: SocialConnection | None = None
) -> dict:
    """Post a tweet for a specific user. Used by scheduler and manual posting."""
    config = EpisodeTweetConfig.query.filter_by(
        episode_id=episode_id, user_id=user_id
    ).with_for_update().first()

    if not config:
        return {'success': False, 'error': 'No tweet configuration found'}

    if config.status == EpisodeTweetConfig.STATUS_POSTED:
        return {'success': False, 'error': 'Tweet already posted'}

    # ... shared posting logic ...
    return {'success': True, 'tweet_url': result.get('tweet_url')}
```

Then route becomes:
```python
def post_tweet_now(podcast_id, episode_id):
    scheduler = TweetSchedulerService()
    result = scheduler.post_tweet_for_user(current_user.id, episode_id)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(result)
    # ... flash/redirect handling
```

**Pros:** Single source of truth, consistent behavior, easier testing
**Cons:** Service method needs to handle both scheduler and manual contexts
**Effort:** Medium
**Risk:** Low

### Solution B: Keep Separate, Extract Helpers

Extract common patterns (content building, log creation) into helper functions, but keep main logic separate.

**Pros:** Less refactoring, maintains flexibility
**Cons:** Still some duplication, two places to maintain
**Effort:** Small
**Risk:** Low

## Recommended Action

**Implement Solution A after fixing P1 issues** - Once the race condition and transaction safety are fixed in the route, refactor to use shared service method.

## Technical Details

**Affected Files:**
- `/Users/austin/Git_Repos/mouse_domination/routes/podcasts/tweets.py` (lines 197-318)
- `/Users/austin/Git_Repos/mouse_domination/services/tweet_scheduler.py` (lines 201-294)

## Acceptance Criteria

- [ ] Single `post_tweet_for_user()` method handles both scheduler and manual posting
- [ ] Route delegates to service, only handles HTTP concerns
- [ ] All existing tests pass
- [ ] Add test that verifies scheduler and manual posting produce identical results

## Work Log

| Date | Action | Outcome |
|------|--------|---------|
| 2026-01-27 | Identified during code review | Created todo |

## Resources

- Pattern Recognition Agent findings
- Architecture Strategist findings on layer violations
