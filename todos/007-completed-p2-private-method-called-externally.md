---
status: completed
priority: p2
issue_id: "007"
tags: [code-review, architecture, encapsulation, pr-22]
dependencies: []
---

# Private Method Called from Route Handler

## Problem Statement

The route handler directly calls `_generate_tweet_content`, which is a private method (indicated by underscore prefix). This breaks encapsulation and creates fragile dependencies on implementation details.

**Why it matters:** Private methods can change without notice; public APIs should be stable.

## Findings

**Location:** `/Users/austin/Git_Repos/mouse_domination/routes/podcasts/tweets.py:160`

```python
scheduler_service = TweetSchedulerService()
content = scheduler_service._generate_tweet_content(config, episode)
```

The underscore prefix `_generate_tweet_content` signals this is an internal implementation detail.

## Proposed Solutions

### Solution A: Create Public Wrapper Method (Recommended)

Add a public method to `TweetSchedulerService`:

```python
def generate_tweet_content_for_config(
    self, config: EpisodeTweetConfig, episode: EpisodeGuide
) -> str | None:
    """
    Generate AI-powered tweet content for a specific config.

    Args:
        config: The tweet config to generate content for
        episode: The episode being tweeted about

    Returns:
        Generated content string or None if generation fails
    """
    return self._generate_tweet_content(config, episode)
```

**Pros:** Clean API boundary, allows internal refactoring
**Cons:** One more method to maintain
**Effort:** Trivial
**Risk:** None

### Solution B: Rename to Public

Simply remove the underscore to make it public: `generate_tweet_content()`

**Pros:** Simplest change
**Cons:** Signals that method was always meant to be public
**Effort:** Trivial
**Risk:** None

## Recommended Action

<!-- To be filled during triage -->

## Technical Details

**Affected files:**
- `services/tweet_scheduler.py` - add public wrapper or rename method
- `routes/podcasts/tweets.py` - update call site

## Acceptance Criteria

- [ ] Route calls a public method (no underscore prefix)
- [ ] Private method remains for internal use
- [ ] Tests updated if method renamed

## Work Log

| Date | Action | Result/Learning |
|------|--------|-----------------|
| 2026-01-25 | Identified during architecture review | architecture-strategist agent |

## Resources

- PR #22: Add automated tweet scheduling
- Python naming conventions: https://peps.python.org/pep-0008/#naming-conventions
