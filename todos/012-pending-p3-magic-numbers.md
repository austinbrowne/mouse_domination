---
status: pending
priority: p3
issue_id: "012"
tags: [code-review, quality, magic-numbers, pr-22]
dependencies: []
---

# Magic Numbers for Twitter Character Limit

## Problem Statement

The Twitter 280-character limit appears as a magic number in multiple places without a named constant.

## Findings

**Locations:**
- `services/tweet_scheduler.py:207` - `if len(content) > 280:`
- `services/tweet_scheduler.py:211` - `max_text = 280 - url_len`
- `services/tweet_scheduler.py:215` - `content = content[:277] + '...'`
- `routes/podcasts/tweets.py:105` - `if len(custom_content) > 280:`

## Proposed Solutions

### Solution A: Extract Constant (Recommended)

```python
# In tweet_scheduler.py or a constants module
TWITTER_MAX_CHARS = 280
ELLIPSIS = '...'
ELLIPSIS_LEN = len(ELLIPSIS)  # 3

# Usage
if len(content) > TWITTER_MAX_CHARS:
    max_text = TWITTER_MAX_CHARS - url_len - ELLIPSIS_LEN
    content = content[:max_text] + ELLIPSIS
```

**Pros:** Single source of truth, self-documenting
**Cons:** Minor overhead
**Effort:** Trivial
**Risk:** None

## Recommended Action

<!-- To be filled during triage -->

## Acceptance Criteria

- [ ] TWITTER_MAX_CHARS constant defined
- [ ] All magic 280s replaced with constant
- [ ] No hardcoded ellipsis length

## Work Log

| Date | Action | Result/Learning |
|------|--------|-----------------|
| 2026-01-25 | Identified during Python review | kieran-python-reviewer agent |

## Resources

- PR #22: Add automated tweet scheduling
