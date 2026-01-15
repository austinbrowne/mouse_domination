# ADR-001: Alpine Sort Drag-and-Drop with x-for Reactivity Fix

## Status
**Accepted** - January 2026

## Context

The Episode Guide edit page allows users to reorder items within sections via drag-and-drop. The implementation uses:
- **Alpine.js** for reactive UI state management
- **Alpine Sort plugin** (@alpinejs/sort) for drag-and-drop functionality
- **x-for** loops to render item lists from a reactive array
- **Flask backend** to persist position changes

### The Problem

When dragging items to reorder them, the behavior was broken in multiple ways:
1. Items would visually snap back to wrong positions after drag
2. Item numbers (1, 2, 3...) wouldn't update to reflect new order
3. Database positions became corrupted with duplicate/invalid values
4. Page refresh was required to see correct state

### Example Scenario
- Before: Items numbered 1 (Uncle), 2 (ATK), 3 (VGN)
- User drags item 3 to position 1
- Expected: 1 (VGN), 2 (Uncle), 3 (ATK)
- Actual: Erratic ordering like 3 (ATK), 1 (VGN), 2 (Uncle)

## Root Cause Analysis

After extensive debugging with multiple specialized agents, we identified **three distinct bugs**:

### Bug 1: Database Refresh Before Commit
**File:** `routes/episode_guide.py`

```python
# BROKEN - refresh overwrites uncommitted changes
item.position = new_position
db.session.refresh(item)  # This reloads OLD position from DB!
db.session.commit()
```

The `db.session.refresh(item)` call was happening BEFORE `commit()`, which caused SQLAlchemy to reload the item from the database, overwriting the position we just set.

### Bug 2: The "Double Swap" Problem
**Root cause:** Conflict between Alpine Sort's DOM manipulation and Alpine's x-for reactivity.

When a user drags an item:
1. **Alpine Sort (SortableJS)** physically moves the DOM element to the new position
2. **Our handler** updates the reactive `items` array
3. **Alpine's x-for** detects the array change and tries to re-render
4. **Conflict:** Alpine doesn't know the DOM was already moved, so it moves elements again

This is a [well-documented issue](https://github.com/alpinejs/alpine/discussions/1635) in the Alpine.js community:

> "The problem is that Alpine does update the elements but those have been moved to a different place by SortableJS resulting in a double swap because Alpine is trying to reuse existing elements and it doesn't know that they are not in the same position anymore."

### Bug 3: Stale Index Values
Even after fixing the double-swap with `Alpine.raw()`, the item numbers (which use `idx` from x-for) wouldn't update because:
- `Alpine.raw()` bypasses reactivity entirely
- The x-for loop never re-runs
- `idx` values remain stale

## Decision

We implemented a **three-part fix**:

### Fix 1: Move Database Refresh After Commit
**File:** `routes/episode_guide.py:575-580`

```python
item.position = new_position

db.session.commit()

# Refresh AFTER commit to get the final committed state
db.session.refresh(item)
```

### Fix 2: Use sortIteration Key Strategy
Instead of `Alpine.raw()` (which prevents number updates), we use a `sortIteration` counter in the x-for key. When incremented, all keys change, forcing Alpine to recreate elements from scratch rather than reconciling existing DOM.

**File:** `templates/episode_guide/edit.html`

```javascript
// In Alpine component data
sortIteration: 0,

// In handleSort, after updating array
this.sortIteration++;
```

```html
<!-- x-for with composite key -->
<template x-for="(item, idx) in items['section'] || []"
          :key="sortIteration + '-' + item.id">
```

**Why this works:**
- Before sort: keys are `0-5`, `0-6`, `0-7`
- After sort: keys become `1-5`, `1-6`, `1-7`
- Alpine sees ALL keys changed → destroys old elements, creates new ones
- New elements have fresh `idx` values from the updated array
- No double-swap because there's no DOM reconciliation

### Fix 3: Proper Array Update Logic
**File:** `templates/episode_guide/edit.html:714-738`

```javascript
async handleSort(itemId, toSection, newPosition) {
    // ... API call to persist ...

    // Update local array to match server state
    if (fromSection === toSection) {
        const oldIndex = this.items[fromSection].findIndex(i => i.id === itemId);
        if (oldIndex !== -1) {
            this.items[fromSection].splice(oldIndex, 1);
            this.items[fromSection].splice(newPosition, 0, data.item);
        }
    } else {
        // Cross-section move
        const oldIndex = this.items[fromSection].findIndex(i => i.id === itemId);
        if (oldIndex !== -1) {
            this.items[fromSection].splice(oldIndex, 1);
        }
        if (!this.items[toSection]) {
            this.items[toSection] = [];
        }
        this.items[toSection].splice(newPosition, 0, data.item);
    }

    // Force x-for to recreate elements with new keys
    this.sortIteration++;
}
```

## Alternative Solutions Considered

### 1. Don't Update Array At All
Let Alpine Sort handle DOM, only persist to server, rely on refresh.
- **Rejected:** Numbers wouldn't update, poor UX

### 2. Alpine.raw() for Non-Reactive Updates
Update array without triggering reactivity.
- **Rejected:** Numbers (using `idx`) wouldn't update

### 3. Reset `_x_prevKeys` Internal State
Manually sync Alpine's internal key tracking.
- **Rejected:** Relies on undocumented internals, fragile

### 4. Wait for Alpine PR #4361
A comprehensive fix is pending in Alpine.js.
- **Rejected:** Not merged yet, unknown timeline

## Implementation Details

### Files Modified

| File | Changes |
|------|---------|
| `routes/episode_guide.py` | Move `db.session.refresh()` after `commit()` |
| `templates/episode_guide/edit.html` | Add `sortIteration`, update `:key`, fix `handleSort` |
| `templates/base.html` | Add Alpine Sort plugin before Alpine core |

### Alpine Sort Setup

```html
<!-- base.html - Plugin must load BEFORE Alpine core -->
<script defer src="https://cdn.jsdelivr.net/npm/@alpinejs/sort@3.x.x/dist/cdn.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
```

```html
<!-- Sortable container -->
<div x-sort="(itemId, newPosition) => handleSort(itemId, 'section_key', newPosition)"
     x-sort:group="episode-guide-items">

    <template x-for="(item, idx) in items['section_key'] || []"
              :key="sortIteration + '-' + item.id">

        <!-- Sortable item -->
        <div x-sort:item="item.id">
            <!-- Drag handle -->
            <div x-sort:handle>⋮⋮</div>

            <!-- Item number using idx -->
            <span x-text="(idx + 1) + '.'"></span>
        </div>
    </template>
</div>
```

### Database Position Normalization

If positions become corrupted, use this script:

```python
# scripts/check_positions.py
from app import create_app
from models import db, EpisodeGuideItem

app = create_app()

def fix_positions():
    """Normalize all positions to 0, 1, 2, ... per section."""
    with app.app_context():
        combos = db.session.query(
            EpisodeGuideItem.guide_id,
            EpisodeGuideItem.section
        ).distinct().all()

        for guide_id, section in combos:
            items = EpisodeGuideItem.query.filter_by(
                guide_id=guide_id,
                section=section
            ).order_by(EpisodeGuideItem.position).all()

            for i, item in enumerate(items):
                if item.position != i:
                    item.position = i

        db.session.commit()
```

Run with: `PYTHONPATH=. python scripts/check_positions.py --fix`

## Consequences

### Positive
- Drag-and-drop works correctly with immediate visual feedback
- Numbers update instantly without page refresh
- Database positions stay consistent
- Works for both same-section and cross-section moves

### Negative
- Small performance overhead: all items in section are recreated on each sort
- For very large lists (100+ items), may notice brief flicker

### Trade-offs
- Chose simplicity and correctness over micro-optimization
- Episode guide sections typically have <30 items, so performance is fine

## References

- [Alpine Sort Plugin Docs](https://alpinejs.dev/plugins/sort)
- [GitHub Discussion #1635 - SortableJS x-for conflict](https://github.com/alpinejs/alpine/discussions/1635)
- [GitHub Discussion #4157 - Sort plugin and x-for](https://github.com/alpinejs/alpine/discussions/4157)
- [GitHub Discussion #4368 - Alpine.raw() solution](https://github.com/alpinejs/alpine/discussions/4368)
- [GitHub PR #4361 - Pending comprehensive fix](https://github.com/alpinejs/alpine/pull/4361)

## Lessons Learned

1. **Always commit before refresh** in SQLAlchemy - `refresh()` reloads from DB
2. **DOM manipulation + reactive frameworks = conflicts** - they fight over DOM control
3. **Key strategy matters** - composite keys can force full re-renders when needed
4. **Spawn specialized debug agents** for complex multi-layer bugs
5. **Research existing solutions** - this was a known issue with documented fixes
