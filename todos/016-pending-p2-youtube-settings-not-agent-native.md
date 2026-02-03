---
status: completed
priority: p2
issue_id: "016"
tags: [code-review, agent-native, api, pr-youtube-title-filter]
dependencies: []
---

# YouTube Title Filter Not Agent-Accessible

## Problem Statement

The YouTube title filter feature (new in this PR) is UI-only. An AI agent cannot programmatically configure the title filter for a podcast because:
1. POST only accepts form data, not JSON
2. GET only returns HTML, not JSON

**Why it matters:** An agent helping manage podcast automation cannot configure which live streams should trigger tweets. This feature was added without agent-native support.

## Findings

**Location:** `/Users/austin/Git_Repos/mouse_domination/routes/podcasts/tweets.py:350-398`

**Current Implementation:**
```python
# Only reads form data
title_filter_enabled = request.form.get('youtube_title_filter_enabled') == 'on'
title_filter = request.form.get('youtube_title_filter', '').strip()
```

**Agent-Native Audit:**
| Action | JSON Input | JSON Output | Agent-Accessible |
|--------|------------|-------------|------------------|
| Read YouTube settings | N/A | NO (HTML) | NO |
| Set channel ID | NO (form only) | NO | NO |
| Enable title filter | NO (form only) | NO | NO |
| Set filter text | NO (form only) | NO | NO |
| Test live detection | Yes | Yes | YES |

**Contrast:** `test_youtube_live()` correctly returns JSON and is fully agent-accessible.

## Proposed Solutions

### Solution A: Add JSON Support to Existing Endpoint (Recommended)

```python
@podcast_bp.route('/<int:podcast_id>/settings/youtube', methods=['GET', 'POST'])
@login_required
@require_podcast_admin
def youtube_settings(podcast_id):
    podcast = g.podcast

    if request.method == 'POST':
        # Accept JSON or form data
        if request.is_json:
            data = request.get_json()
            channel_id = data.get('youtube_channel_id', '').strip()
            title_filter_enabled = data.get('youtube_title_filter_enabled', False)
            title_filter = data.get('youtube_title_filter', '').strip()
        else:
            channel_id = request.form.get('youtube_channel_id', '').strip()
            title_filter_enabled = request.form.get('youtube_title_filter_enabled') == 'on'
            title_filter = request.form.get('youtube_title_filter', '').strip()

        # ... validation and save logic ...

        # Return JSON for API clients
        if request.is_json or request.headers.get('Accept') == 'application/json':
            return jsonify({
                'success': True,
                'youtube_channel_id': podcast.youtube_channel_id,
                'youtube_title_filter': podcast.youtube_title_filter,
                'youtube_title_filter_enabled': podcast.youtube_title_filter_enabled,
            })

    # GET: Return JSON if requested
    if request.headers.get('Accept') == 'application/json':
        return jsonify({
            'youtube_channel_id': podcast.youtube_channel_id,
            'youtube_title_filter': podcast.youtube_title_filter,
            'youtube_title_filter_enabled': podcast.youtube_title_filter_enabled,
        })

    return render_template(...)
```

**Pros:** Single endpoint, backward compatible
**Cons:** Slightly more complex endpoint
**Effort:** Small
**Risk:** Low

### Solution B: Separate API Endpoint

Create `/api/podcasts/<id>/youtube-settings` for JSON access.

**Pros:** Clean separation of concerns
**Cons:** Two endpoints to maintain
**Effort:** Medium
**Risk:** Low

## Recommended Action

**Implement Solution A** - Add JSON support to the existing endpoint. This maintains backward compatibility while enabling agent access.

## Technical Details

**Affected Files:**
- `/Users/austin/Git_Repos/mouse_domination/routes/podcasts/tweets.py` (lines 350-398)

**Also update `Podcast.to_dict()`:**
```python
# In models/podcast.py, add to to_dict():
'youtube_title_filter': self.youtube_title_filter,
'youtube_title_filter_enabled': self.youtube_title_filter_enabled,
```

## Acceptance Criteria

- [ ] POST endpoint accepts JSON body with `Content-Type: application/json`
- [ ] GET endpoint returns JSON when `Accept: application/json` header present
- [ ] Existing form-based flow continues to work
- [ ] `Podcast.to_dict()` includes title filter fields
- [ ] Add API tests for JSON input/output

## Work Log

| Date | Action | Outcome |
|------|--------|---------|
| 2026-01-27 | Identified during code review | Created todo |

## Resources

- Agent-Native Reviewer findings
- Flask request handling: https://flask.palletsprojects.com/en/2.0.x/api/#flask.Request.is_json
