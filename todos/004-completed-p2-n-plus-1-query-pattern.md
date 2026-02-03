---
status: completed
priority: p2
issue_id: "004"
tags: [code-review, performance, database, pr-22]
dependencies: []
---

# N+1 Query Pattern in create_tweet_configs_for_episode

## Problem Statement

The `create_tweet_configs_for_episode` method executes N+1 database queries when creating tweet configs for podcast members.

**Why it matters:** For a podcast with N members, this executes N+1 queries instead of 2. At scale (50+ members), this significantly impacts performance.

## Findings

**Location:** `/Users/austin/Git_Repos/mouse_domination/services/tweet_scheduler.py:332-341`

```python
for member in members:
    # Check if config already exists - N queries!
    existing = EpisodeTweetConfig.query.filter_by(
        episode_id=episode.id,
        user_id=member.user_id,
    ).first()
```

**Impact:**
- 10 members: 11 queries
- 50 members: 51 queries
- 100 members: 101 queries

## Proposed Solutions

### Solution A: Batch Fetch Existing Configs (Recommended)

```python
# Fetch all existing configs in one query
existing_configs = {
    c.user_id: c
    for c in EpisodeTweetConfig.query.filter(
        EpisodeTweetConfig.episode_id == episode.id,
        EpisodeTweetConfig.user_id.in_([m.user_id for m in members])
    ).all()
}

for member in members:
    existing = existing_configs.get(member.user_id)
    if existing:
        configs.append(existing)
        continue
    # ... create new config
```

**Pros:** Reduces N+1 to 2 queries regardless of member count
**Cons:** Slightly more complex code
**Effort:** Small
**Risk:** None

## Recommended Action

<!-- To be filled during triage -->

## Technical Details

**Affected files:**
- `services/tweet_scheduler.py` - `create_tweet_configs_for_episode()` method

## Acceptance Criteria

- [ ] Only 2 database queries executed regardless of member count
- [ ] Functionality unchanged
- [ ] Add query logging to verify

## Work Log

| Date | Action | Result/Learning |
|------|--------|-----------------|
| 2026-01-25 | Identified during performance review | performance-oracle agent |

## Resources

- PR #22: Add automated tweet scheduling
- SQLAlchemy IN clause: https://docs.sqlalchemy.org/en/20/core/sqlelement.html#sqlalchemy.sql.expression.ColumnElement.in_
