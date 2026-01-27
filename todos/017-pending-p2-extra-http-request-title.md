---
status: completed
priority: p2
issue_id: "017"
tags: [code-review, performance, http, pr-youtube-title-filter]
dependencies: []
---

# Extra HTTP Request for Video Title in Redirect Path

## Problem Statement

When YouTube responds with a redirect (302) to indicate a live stream, the code makes **two HTTP requests**: first a HEAD request, then a separate GET to fetch the video title. This doubles latency in the live detection path.

**Why it matters:** At scale (100+ podcasts), this adds significant latency and increases risk of YouTube rate limiting.

## Findings

**Location:** `/Users/austin/Git_Repos/mouse_domination/services/youtube_live.py:66-94`

**Current Flow (redirect case):**
```python
# Request 1: HEAD to /channel/{id}/live
response = requests.head(live_url, allow_redirects=False, ...)

if response.status_code in (301, 302, 303, 307, 308):
    redirect_url = response.headers.get('Location', '')
    video_id = self._extract_video_id(redirect_url)

    if video_id:
        # Request 2: GET to /watch?v={video_id} for title
        video_title = self._fetch_video_title(video_id)  # Extra request!
```

**Performance Impact:**
- Current: 2 requests × 100-500ms = 200-1000ms per live check
- With fix: 1 request × 100-500ms = 100-500ms per live check
- At 100 podcasts: Saves 10-50 seconds per scheduler cycle

**Contrast:** The non-redirect path (lines 98-119) correctly extracts title from the same GET response used for live verification.

## Proposed Solutions

### Solution A: Follow Redirect with GET (Recommended)

Instead of HEAD + separate GET, follow the redirect with a single GET:

```python
if response.status_code in (301, 302, 303, 307, 308):
    redirect_url = response.headers.get('Location', '')
    video_id = self._extract_video_id(redirect_url)

    if video_id:
        # Follow redirect to get both live verification AND title
        video_response = requests.get(
            redirect_url,
            timeout=self.timeout,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; PodcastBot/1.0)'}
        )

        # Verify it's actually live AND extract title from same response
        if self._is_live_page(video_response.text):
            video_title = self._extract_title_from_html(video_response.text)
            return {
                'is_live': True,
                'video_id': video_id,
                'video_url': f'https://www.youtube.com/watch?v={video_id}',
                'video_title': video_title,
                'error': None,
            }
```

**Pros:** Halves HTTP requests, more reliable live verification
**Cons:** Slightly more data transferred (full page vs title only)
**Effort:** Small
**Risk:** Low

### Solution B: Remove Title from Redirect Path

Only fetch title in the GET fallback path, skip it for redirects.

**Pros:** Minimal change
**Cons:** Inconsistent - some live streams would have titles, others wouldn't
**Effort:** Minimal
**Risk:** Medium (breaks title filter feature for some streams)

## Recommended Action

**Implement Solution A** - Follow redirect with GET to verify live status AND extract title in single request.

## Technical Details

**Affected Files:**
- `/Users/austin/Git_Repos/mouse_domination/services/youtube_live.py` (lines 66-94)

**Refactored Flow:**
1. HEAD request to `/channel/{id}/live`
2. If redirect: Follow with GET to verify live + extract title
3. If no redirect: GET fallback (existing logic)

## Acceptance Criteria

- [ ] Redirect path makes only 1 additional request (not 2)
- [ ] Video title is still extracted in redirect path
- [ ] Live verification still works correctly
- [ ] Tests pass including title extraction tests
- [ ] Add performance test comparing request counts

## Work Log

| Date | Action | Outcome |
|------|--------|---------|
| 2026-01-27 | Identified during code review | Created todo |

## Resources

- Performance Oracle findings
- requests library docs: https://docs.python-requests.org/en/latest/user/quickstart/#redirection-and-history
