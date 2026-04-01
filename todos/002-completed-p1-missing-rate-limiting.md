---
status: completed
priority: p1
issue_id: "002"
tags: [code-review, security, rate-limiting, pr-22]
dependencies: []
---

# Missing Rate Limiting on Tweet API Endpoints

## Problem Statement

New tweet-related endpoints lack rate limiting, despite the application having Flask-Limiter configured. Existing social routes like `post_snippet` have `@limiter.limit("10 per minute")` applied, but the new routes don't.

**Why it matters:**
- AI generation endpoints could be abused to run up API costs (OpenAI/Anthropic billing)
- YouTube test endpoint could be used as a proxy for abuse
- General resource exhaustion attacks possible

## Findings

**Affected endpoints:**

1. `POST /episodes/<episode_id>/tweets/generate` (lines 132-193)
   - Triggers AI content generation (expensive operation)
   - No rate limiting

2. `POST /episodes/<episode_id>/tweets/create-all` (lines 196-231)
   - Creates multiple configs with AI generation for each member
   - No rate limiting

3. `POST /settings/youtube/test` (lines 281-311)
   - Makes external HTTP requests to YouTube
   - No rate limiting

**Location:** `/Users/austin/Git_Repos/mouse_domination/routes/podcasts/tweets.py`

**Comparison:** Existing routes in `routes/content_atomizer.py` and `routes/auth.py` properly use `@limiter.limit()`.

## Proposed Solutions

### Solution A: Add Standard Rate Limits (Recommended)

```python
from extensions import limiter

@podcast_bp.route('/<int:podcast_id>/episodes/<int:episode_id>/tweets/generate', methods=['POST'])
@login_required
@require_podcast_access
@limiter.limit("5 per minute")
def generate_tweet(podcast_id, episode_id):
    ...

@podcast_bp.route('/<int:podcast_id>/episodes/<int:episode_id>/tweets/create-all', methods=['POST'])
@login_required
@require_podcast_access
@limiter.limit("2 per minute")
def create_all_tweet_configs(podcast_id, episode_id):
    ...

@podcast_bp.route('/<int:podcast_id>/settings/youtube/test', methods=['POST'])
@login_required
@require_podcast_access
@limiter.limit("10 per minute")
def test_youtube_live(podcast_id):
    ...
```

**Pros:** Simple, consistent with existing patterns
**Cons:** None
**Effort:** Small
**Risk:** None

## Recommended Action

<!-- To be filled during triage -->

## Technical Details

**Affected files:**
- `routes/podcasts/tweets.py`

**Import needed:**
```python
from extensions import limiter
```

## Acceptance Criteria

- [ ] `generate_tweet` limited to 5/minute
- [ ] `create_all_tweet_configs` limited to 2/minute
- [ ] `test_youtube_live` limited to 10/minute
- [ ] Rate limit exceeded returns 429 status code

## Work Log

| Date | Action | Result/Learning |
|------|--------|-----------------|
| 2026-01-25 | Identified during security review | security-sentinel agent flagged this |

## Resources

- PR #22: Add automated tweet scheduling
- Flask-Limiter docs: https://flask-limiter.readthedocs.io/
