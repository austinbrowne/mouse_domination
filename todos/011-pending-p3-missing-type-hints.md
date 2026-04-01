---
status: pending
priority: p3
issue_id: "011"
tags: [code-review, quality, type-hints, pr-22]
dependencies: []
---

# Missing Type Hints on Routes and Functions

## Problem Statement

Routes lack type annotations for parameters and return types. While not strictly required, consistency with the service layer (which has type hints) would improve code quality.

## Findings

**Routes without type hints:**
- `routes/podcasts/tweets.py:25` - `def episode_tweets(podcast_id, episode_id):`
- `routes/podcasts/tweets.py:64` - `def my_tweet_config(podcast_id, episode_id):`
- `routes/podcasts/tweets.py:135` - `def generate_tweet(podcast_id, episode_id):`
- All other routes in the file

**Scheduler functions:**
- `services/scheduler.py:25` - `def init_scheduler(app: Flask):` - missing return type

**Vague return types:**
- `services/tweet_scheduler.py:311` - `-> list` should be `-> list[EpisodeTweetConfig]`

## Proposed Solutions

### Solution A: Add Type Hints (Recommended)

```python
from flask import Response

def episode_tweets(podcast_id: int, episode_id: int) -> str:
    ...

def my_tweet_config(podcast_id: int, episode_id: int) -> str | Response:
    ...

def init_scheduler(app: Flask) -> None:
    ...

def create_tweet_configs_for_episode(
    self, episode: EpisodeGuide, generate_content: bool = True
) -> list[EpisodeTweetConfig]:
    ...
```

**Pros:** Better IDE support, documentation
**Cons:** More verbose
**Effort:** Small
**Risk:** None

## Recommended Action

<!-- To be filled during triage -->

## Acceptance Criteria

- [ ] All route functions have parameter and return type hints
- [ ] Service methods have specific return types (not just `list`)
- [ ] mypy or pyright passes without errors

## Work Log

| Date | Action | Result/Learning |
|------|--------|-----------------|
| 2026-01-25 | Identified during Python review | kieran-python-reviewer agent |

## Resources

- PR #22: Add automated tweet scheduling
- PEP 484: https://peps.python.org/pep-0484/
