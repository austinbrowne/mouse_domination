---
status: pending
priority: p2
issue_id: "009"
tags: [code-review, agent-native, api, pr-22]
dependencies: []
---

# No JSON API for Agent-Native Access

## Problem Statement

The tweet scheduling features are implemented as UI-only (form submissions returning HTML). There are no JSON API endpoints for programmatic control, limiting automation capabilities.

**Why it matters:** An AI agent helping manage podcast tweet automation cannot perform most actions - only 2 of 12 capabilities are agent-accessible.

## Findings

**Agent-Native Audit Results:**

| Capability | Status |
|------------|--------|
| View episode tweet configs | **UI-Only** |
| Edit my tweet config | **UI-Only** |
| Generate AI tweet content | Partial (XHR) |
| Create all team configs | **UI-Only** |
| Configure YouTube channel | **UI-Only** |
| Test YouTube live detection | OK (JSON) |
| Check scheduler status | **Missing** |
| Trigger manual live check | **Missing** |
| List all pending tweets | **Missing** |
| Retry failed tweets | **Missing** |

**Score:** 2/12 capabilities agent-accessible

## Proposed Solutions

### Solution A: Add JSON API Endpoints (Recommended)

Create `/api/podcasts/` routes mirroring UI routes:

```python
# In routes/podcasts/tweets.py

@podcast_bp.route('/api/<int:podcast_id>/episodes/<int:episode_id>/tweets')
@login_required
@require_podcast_access
def api_episode_tweets(podcast_id, episode_id):
    """API: List all tweet configs for an episode."""
    configs = EpisodeTweetConfig.query.filter_by(episode_id=episode_id).all()
    return jsonify({'tweets': [c.to_dict() for c in configs]})

@podcast_bp.route('/api/<int:podcast_id>/episodes/<int:episode_id>/tweets/<int:config_id>', methods=['PUT'])
@login_required
@require_podcast_access
def api_update_tweet_config(podcast_id, episode_id, config_id):
    """API: Update a tweet config."""
    config = EpisodeTweetConfig.query.get_or_404(config_id)
    data = request.get_json()
    # ... update logic
    return jsonify(config.to_dict())
```

**Pros:** Full agent access to all features
**Cons:** More endpoints to maintain
**Effort:** Medium
**Risk:** Low

### Solution B: Content-Type Negotiation

Modify existing routes to return JSON when `Accept: application/json` header present.

**Pros:** Single set of routes
**Cons:** More complex route logic
**Effort:** Medium
**Risk:** Low

## Recommended Action

<!-- To be filled during triage -->

## Technical Details

**Needed endpoints:**
- `GET /api/podcasts/<id>/episodes/<id>/tweets` - List configs
- `GET /api/podcasts/<id>/episodes/<id>/tweets/<id>` - Get single config
- `POST /api/podcasts/<id>/episodes/<id>/tweets` - Create config
- `PUT /api/podcasts/<id>/episodes/<id>/tweets/<id>` - Update config
- `DELETE /api/podcasts/<id>/episodes/<id>/tweets/<id>` - Delete config
- `GET /api/scheduler/status` - Scheduler status
- `POST /api/scheduler/trigger` - Manual trigger

## Acceptance Criteria

- [ ] All CRUD operations available via JSON API
- [ ] Scheduler status queryable
- [ ] Manual trigger endpoint available
- [ ] API documented

## Work Log

| Date | Action | Result/Learning |
|------|--------|-----------------|
| 2026-01-25 | Identified during agent-native review | agent-native-reviewer agent |

## Resources

- PR #22: Add automated tweet scheduling
- Existing API pattern: `routes/content_atomizer.py`
