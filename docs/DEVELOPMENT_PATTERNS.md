# Development Patterns

This document captures coding patterns and conventions for the Mouse Domination codebase.

---

## Live Search (AJAX-based)

**Pattern:** Server-rendered HTML fragments with client-side fetch

**Why this approach:**
- Single source of truth for rendering (Jinja templates)
- No duplication of rendering logic in JavaScript
- Less client-side code to maintain
- Consistent with full page load rendering

### Implementation

#### 1. Route Handler

Add a query parameter check to return just the HTML fragment:

```python
@blueprint.route('/')
@login_required
def list_items():
    # ... filtering logic ...

    # Check if this is an AJAX request for just the table
    if request.args.get('ajax') == '1':
        return render_template('module/_table.html', items=items, ...)

    # Full page render
    return render_template('module/list.html', items=items, ...)
```

#### 2. Template Structure

Split the table into a partial template:

```
templates/module/
├── list.html           # Full page (extends base.html)
└── _table.html         # Table body partial (no extends)
```

**list.html:**
```html
{% extends "base.html" %}
{% block content %}
<!-- filters -->
<div id="results-container">
    {% include "module/_table.html" %}
</div>
{% endblock %}
```

**_table.html:**
```html
<table class="w-full">
    <thead>...</thead>
    <tbody>
        {% for item in items %}
        <tr>...</tr>
        {% endfor %}
    </tbody>
</table>
<!-- pagination if needed -->
```

#### 3. JavaScript (Alpine.js)

```javascript
function searchFilters() {
    return {
        search: '{{ search or "" }}',
        loading: false,

        async applyFilters() {
            this.loading = true;
            const params = new URLSearchParams();
            if (this.search) params.set('search', this.search);
            params.set('ajax', '1');

            try {
                const response = await fetch('{{ url_for("module.list_items") }}?' + params.toString());
                const html = await response.text();
                document.getElementById('results-container').innerHTML = html;
            } catch (error) {
                console.error('Search failed:', error);
            }

            this.loading = false;
        }
    }
}
```

#### 4. Loading State (Optional)

Show a loading indicator while fetching:

```html
<div id="results-container" :class="{ 'opacity-50': loading }">
    {% include "module/_table.html" %}
</div>
```

### Pages Using This Pattern

- `/inventory/` - Inventory list with search and filters
- `/episode-guide/` - Episode guide with search
- (Add new pages here as implemented)

---

## Form Validation

**Pattern:** Use `type="text"` for optional URL/email fields

HTML5 validation (`type="url"`, `type="email"`) blocks form submission if the field is filled with an invalid value, even if the field is optional. For optional fields, use `type="text"` to avoid blocking form submission.

```html
<!-- Good: Optional URL field -->
<input type="text" name="website" placeholder="https://...">

<!-- Bad: Will block submission if invalid -->
<input type="url" name="website" placeholder="https://...">
```

---

## Inline Editable Fields

**Pattern:** Alpine.js dropdown with AJAX update

For fields that should be editable directly in list views (like status dropdowns):

#### 1. Route Handler

```python
@blueprint.route('/<int:id>/update-field', methods=['POST'])
@login_required
def update_field(id):
    item = Model.query.filter_by(id=id, user_id=current_user.id).first_or_404()

    field = request.form.get('field')
    value = request.form.get('value')

    if field == 'status':
        if value not in VALID_VALUES:
            return jsonify({'success': False, 'error': 'Invalid value'}), 400
        item.status = value

    db.session.commit()
    return jsonify({'success': True})
```

#### 2. JavaScript Component

```javascript
function inlineDropdown(itemId, field, initialValue) {
    return {
        open: false,
        value: initialValue,
        saving: false,

        async updateField(newValue) {
            if (this.value === newValue) {
                this.open = false;
                return;
            }

            this.saving = true;
            const formData = new FormData();
            formData.append('field', field);
            formData.append('value', newValue);
            formData.append('csrf_token', '{{ csrf_token() }}');

            const response = await fetch(`/module/${itemId}/update-field`, {
                method: 'POST',
                body: formData
            });

            const data = await response.json();
            if (data.success) {
                this.value = newValue;
            }

            this.saving = false;
            this.open = false;
        }
    }
}
```

---

## Modern Dropdown Filters

**Pattern:** Alpine.js custom dropdowns (not native `<select>`)

Native `<select>` elements are difficult to style consistently. Use Alpine.js for custom dropdown UI:

```html
<div x-data="{ open: false }" @click.away="open = false" class="relative">
    <button @click="open = !open" class="...">
        <span x-text="currentLabel"></span>
        <svg><!-- chevron --></svg>
    </button>
    <div x-show="open" x-transition class="absolute z-20 mt-1 ...">
        <button @click="selectOption('value1')">Option 1</button>
        <button @click="selectOption('value2')">Option 2</button>
    </div>
</div>
```

---

## Local Development

Run the Flask development server for local testing:

```bash
# Start PostgreSQL (if not running)
docker compose -f deploy/docker-compose.dev.yml up -d

# Run Flask dev server
flask run --port 5001
# Access at http://127.0.0.1:5001
```

The dev server auto-reloads on code changes. No restart needed.
