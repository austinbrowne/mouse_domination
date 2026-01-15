# Pattern: Alpine Sort with x-for (Drag-and-Drop Lists)

## Quick Reference

When using Alpine Sort (`x-sort`) with `x-for` reactive loops, you MUST use the **sortIteration key pattern** to prevent the "double swap" visual glitch.

## The Problem

Alpine Sort (SortableJS) moves DOM elements directly. Alpine's x-for then tries to reconcile the DOM with your array, causing elements to jump around erratically.

## The Solution

```html
<div x-data="{
    items: [...],
    sortIteration: 0,

    async handleSort(itemId, newPosition) {
        // 1. Persist to backend
        await fetch('/api/reorder', { ... });

        // 2. Update local array
        const oldIndex = this.items.findIndex(i => i.id === itemId);
        const [item] = this.items.splice(oldIndex, 1);
        this.items.splice(newPosition, 0, item);

        // 3. CRITICAL: Increment to force re-render
        this.sortIteration++;
    }
}">

    <div x-sort="(id, pos) => handleSort(id, pos)">
        <!-- KEY MUST INCLUDE sortIteration -->
        <template x-for="(item, idx) in items" :key="sortIteration + '-' + item.id">
            <div x-sort:item="item.id">
                <span x-sort:handle>⋮⋮</span>
                <span x-text="(idx + 1) + '. ' + item.name"></span>
            </div>
        </template>
    </div>

</div>
```

## Why It Works

| Step | What Happens |
|------|--------------|
| Before sort | Keys: `0-1`, `0-2`, `0-3` |
| User drags item | Alpine Sort moves DOM element |
| Handler runs | Array updated, `sortIteration++` |
| After sort | Keys: `1-1`, `1-2`, `1-3` |
| Result | Alpine sees ALL keys changed, recreates elements fresh |

By making Alpine think all items are "new", it doesn't try to reconcile existing DOM elements (which were already moved).

## Required Setup

```html
<!-- base.html - Sort plugin BEFORE Alpine core -->
<script defer src="https://cdn.jsdelivr.net/npm/@alpinejs/sort@3.x.x/dist/cdn.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
```

## Directives Reference

| Directive | Purpose |
|-----------|---------|
| `x-sort="handler"` | Container, receives `(itemId, newPosition)` |
| `x-sort:item="id"` | Marks sortable item, provides ID to handler |
| `x-sort:handle` | Optional drag handle element |
| `x-sort:group="name"` | Enable cross-list dragging |

## Common Mistakes

### DON'T: Use item.id alone as key
```html
<!-- BAD - causes double swap -->
<template x-for="item in items" :key="item.id">
```

### DON'T: Use Alpine.raw() if you need idx updates
```javascript
// BAD - numbers won't update
const raw = Alpine.raw(this.items);
raw.splice(...);
```

### DON'T: Forget sortIteration++
```javascript
// BAD - visual glitch will occur
this.items.splice(...);
// Missing: this.sortIteration++;
```

## Backend Considerations

If persisting to database with SQLAlchemy:

```python
# CORRECT - commit BEFORE refresh
item.position = new_position
db.session.commit()
db.session.refresh(item)  # Now safe to refresh

# WRONG - refresh overwrites uncommitted changes
item.position = new_position
db.session.refresh(item)  # Reloads OLD position!
db.session.commit()
```

## Performance Note

The sortIteration pattern recreates all elements on each sort. This is fine for lists under ~100 items. For larger lists, consider virtualization or a different approach.

## See Also

- [ADR-001: Full implementation details](../adr/001-alpine-sort-drag-drop-fix.md)
- [Alpine Sort Docs](https://alpinejs.dev/plugins/sort)
