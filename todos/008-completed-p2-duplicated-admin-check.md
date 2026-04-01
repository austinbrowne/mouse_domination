---
status: completed
priority: p2
issue_id: "008"
tags: [code-review, architecture, duplication, pr-22]
dependencies: []
---

# Duplicated Admin Check Logic

## Problem Statement

Two routes manually check for admin role instead of using the existing `@require_podcast_admin` decorator, creating code duplication and inconsistent error handling.

**Why it matters:** DRY violation; if admin check logic changes, multiple places need updating.

## Findings

**Locations:**
1. `/Users/austin/Git_Repos/mouse_domination/routes/podcasts/tweets.py:207-215`
2. `/Users/austin/Git_Repos/mouse_domination/routes/podcasts/tweets.py:241-248`

```python
# Duplicated in both places:
member = next(
    (m for m in podcast.members if m.user_id == current_user.id),
    None
)
if not member or member.role != 'admin':
    flash('Only podcast admins can...', 'error')
    return redirect(...)
```

**Existing decorator:** `@require_podcast_admin` is already used in `routes/podcasts/discord.py`

## Proposed Solutions

### Solution A: Use Existing Decorator (Recommended)

```python
from utils.podcast_access import require_podcast_admin

@podcast_bp.route('/<int:podcast_id>/episodes/<int:episode_id>/tweets/create-all', methods=['POST'])
@login_required
@require_podcast_admin  # Use this instead of @require_podcast_access
def create_all_tweet_configs(podcast_id, episode_id):
    # Remove manual admin check
    ...

@podcast_bp.route('/<int:podcast_id>/settings/youtube', methods=['GET', 'POST'])
@login_required
@require_podcast_admin  # Use this instead of @require_podcast_access
def youtube_settings(podcast_id):
    # Remove manual admin check
    ...
```

**Pros:** Consistent with existing patterns, removes 15+ lines of duplicate code
**Cons:** None
**Effort:** Trivial
**Risk:** None

## Recommended Action

<!-- To be filled during triage -->

## Technical Details

**Affected files:**
- `routes/podcasts/tweets.py` - two routes need updating

**Changes:**
1. Replace `@require_podcast_access` with `@require_podcast_admin`
2. Remove manual admin check code blocks

## Acceptance Criteria

- [ ] Both routes use `@require_podcast_admin` decorator
- [ ] Manual admin check code removed
- [ ] Non-admin users get appropriate error response

## Work Log

| Date | Action | Result/Learning |
|------|--------|-----------------|
| 2026-01-25 | Identified during pattern review | pattern-recognition-specialist agent |

## Resources

- PR #22: Add automated tweet scheduling
- Existing usage: `routes/podcasts/discord.py`
