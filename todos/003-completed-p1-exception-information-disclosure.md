---
status: completed
priority: p1
issue_id: "003"
tags: [code-review, security, information-disclosure, pr-22]
dependencies: []
---

# Information Disclosure via Exception Message Leakage

## Problem Statement

The `test_youtube_live` endpoint returns raw exception messages to the client via `str(e)`, which may contain sensitive internal details.

**Why it matters:** Exception messages may reveal:
- Internal file paths
- Database connection strings
- Stack trace details
- Third-party service error messages revealing API configuration

## Findings

**Location:** `/Users/austin/Git_Repos/mouse_domination/routes/podcasts/tweets.py:306-311`

```python
except Exception as e:
    log_exception(e, 'Failed to test YouTube live detection')
    return jsonify({
        'success': False,
        'error': str(e),  # VULNERABILITY: Leaks internal error details
    })
```

**Exploitability:** Low - requires triggering specific error conditions, but any authenticated user with podcast access could attempt this.

## Proposed Solutions

### Solution A: Generic Error Message (Recommended)

Replace raw exception with user-friendly message:

```python
except Exception as e:
    log_exception(e, 'Failed to test YouTube live detection')
    return jsonify({
        'success': False,
        'error': 'An error occurred while testing YouTube live detection. Please check the channel ID and try again.',
    })
```

**Pros:** Simple, secure, maintains good UX
**Cons:** Less debugging info for users (but logs capture details)
**Effort:** Trivial
**Risk:** None

### Solution B: Error Classification

Provide specific messages for known error types:

```python
except requests.Timeout:
    return jsonify({'success': False, 'error': 'Request timed out. YouTube may be slow.'})
except requests.ConnectionError:
    return jsonify({'success': False, 'error': 'Could not connect to YouTube.'})
except Exception as e:
    log_exception(e, 'Failed to test YouTube live detection')
    return jsonify({'success': False, 'error': 'An unexpected error occurred.'})
```

**Pros:** More helpful error messages
**Cons:** More code
**Effort:** Small
**Risk:** None

## Recommended Action

<!-- To be filled during triage -->

## Technical Details

**Affected files:**
- `routes/podcasts/tweets.py` line 310

## Acceptance Criteria

- [ ] No raw exception messages returned to client
- [ ] Error response includes user-friendly message
- [ ] Original exception still logged for debugging

## Work Log

| Date | Action | Result/Learning |
|------|--------|-----------------|
| 2026-01-25 | Identified during security review | security-sentinel agent flagged as MEDIUM severity |

## Resources

- PR #22: Add automated tweet scheduling
- OWASP Error Handling: https://owasp.org/www-community/Improper_Error_Handling
