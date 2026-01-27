---
status: completed
priority: p2
issue_id: "005"
tags: [code-review, performance, http, scheduler, pr-22]
dependencies: []
---

# Sequential HTTP Requests for Multiple Podcasts

## Problem Statement

The scheduler checks YouTube live status for each podcast sequentially. With multiple podcasts and network latency, this creates a significant bottleneck.

**Why it matters:** With 10 podcasts and 10-second timeout per request, worst case is 200 seconds of blocking - far exceeding the 3-minute check interval.

## Findings

**Location:** `/Users/austin/Git_Repos/mouse_domination/services/tweet_scheduler.py:59-72`

```python
for podcast in podcasts:
    try:
        result = self._check_podcast_live(podcast)  # Makes HTTP request
        results.append(result)
```

**Impact at scale:**
- 10 podcasts: up to 200 seconds (3+ minutes)
- 50 podcasts: up to 1000 seconds (16+ minutes)
- The 3-minute scheduler interval becomes meaningless

## Proposed Solutions

### Solution A: ThreadPoolExecutor for Concurrent Requests (Recommended)

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def check_and_post_live_tweets(self):
    podcasts = Podcast.query.filter(...).all()
    results = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(self._check_podcast_live, podcast): podcast
            for podcast in podcasts
        }
        for future in as_completed(futures, timeout=30):
            try:
                results.append(future.result())
            except Exception as e:
                app.logger.error(f'Live check failed: {e}')
    return results
```

**Pros:** 10x speedup for I/O-bound operations
**Cons:** Slightly more complex error handling
**Effort:** Medium
**Risk:** Low

### Solution B: Async/Await with aiohttp

Convert to async implementation using aiohttp.

**Pros:** Even more efficient for many concurrent requests
**Cons:** Larger refactor, requires async-compatible scheduler
**Effort:** Large
**Risk:** Medium

## Recommended Action

<!-- To be filled during triage -->

## Technical Details

**Affected files:**
- `services/tweet_scheduler.py` - `check_and_post_live_tweets()` method

## Acceptance Criteria

- [ ] Multiple podcasts checked concurrently (up to 10 at once)
- [ ] Total check time under 30 seconds for 10 podcasts
- [ ] Errors for one podcast don't block others
- [ ] Add timing logs to verify improvement

## Work Log

| Date | Action | Result/Learning |
|------|--------|-----------------|
| 2026-01-25 | Identified during performance review | performance-oracle agent |

## Resources

- PR #22: Add automated tweet scheduling
- Python concurrent.futures: https://docs.python.org/3/library/concurrent.futures.html
