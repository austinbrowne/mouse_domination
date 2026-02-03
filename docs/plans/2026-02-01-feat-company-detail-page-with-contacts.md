---
title: "feat: Add company detail page showing associated contacts"
type: feat
date: 2026-02-01
---

# feat: Add company detail page showing associated contacts

## Overview

Create a dedicated company detail/view page that displays company information and lists all contacts associated with that company. Currently, companies have no view page — the only way to see company details is through the edit form, and there's no way to see which contacts belong to a company without filtering the contacts list.

## Problem Statement

When a user opens a company, they land on the edit form. There's no read-only overview that shows:
- Company details at a glance (status, category, affiliate info)
- The contacts linked to this company
- Quick navigation to related entities

The data relationship already exists (`Contact.company_id → Company.id`), and the company list already shows contact counts — but clicking through to see *who* those contacts are requires leaving the company context entirely.

## Proposed Solution

Add a `GET /companies/<id>` detail route and `templates/companies/view.html` template that shows:
1. Company information in a read-only card layout
2. A contacts table listing all contacts with `company_id == <this company>`, sorted by name
3. Action buttons (Edit Company, Add Contact for this company)

## Technical Approach

### Architecture

This is a straightforward read-only view page. No new models, no API endpoints, no JavaScript complexity.

**Key files to create/modify:**

| File | Action | Purpose |
|------|--------|---------|
| `routes/companies.py` | Modify | Add `view_company(id)` route, update post-edit redirect |
| `templates/companies/view.html` | Create | Company detail page with contacts list |
| `templates/companies/list.html` | Modify | Make company names link to detail page |
| `routes/contacts.py` | Modify | Support `?company_id=` pre-fill on new contact form |
| `templates/contacts/form.html` | Modify | Pre-select company dropdown from query param |

### Route: `GET /companies/<int:id>`

```python
from sqlalchemy.orm import joinedload

@companies_bp.route('/<int:id>')
@login_required
def view_company(id):
    company = Company.query.options(
        joinedload(Company.contacts)
    ).get_or_404(id)
    # Sort contacts by name for consistent display
    contacts = sorted(company.contacts, key=lambda c: (c.name or '').lower())
    return render_template('companies/view.html', company=company, contacts=contacts)
```

Use `joinedload(Company.contacts)` to eager-load contacts in a single query. Sort in Python since the relationship doesn't support order_by with joinedload cleanly.

**Post-edit redirect change:** Update `edit_company` to redirect to the detail page instead of the list:
```python
return redirect(url_for('companies.view_company', id=company.id))
```

### Template: `companies/view.html`

Layout (simpler than `episodes/view.html` — flat card layout, no complex nesting):

1. **Header card** — Company name, category badge, status badge, priority badge, website link (prepend `https://` if no protocol)
2. **Affiliate info card** — Show when `affiliate_status != 'no'`. Displays status, code, link, commission rate
3. **Notes card** — Show only when `company.notes` is not empty. Use `whitespace-pre-line` CSS to preserve line breaks
4. **Contacts section** — Table of associated contacts sorted by name, with columns:
   - Name (linked to contact edit page)
   - Role (badge)
   - Email (or "-")
   - Relationship status (badge)
   - Last contact date (or "-")
5. **Empty state** — "No contacts yet" with "Add Contact" button if zero contacts
6. **Action buttons** — Edit Company, Back to Companies

### Contact pre-fill support

Add `?company_id=` query param support to `routes/contacts.py` `new_contact()`:

```python
# In GET handler, read company_id from query string
preselect_company_id = request.args.get('company_id', type=int)
return render_template('contacts/form.html', contact=None,
                       companies=companies, preselect_company_id=preselect_company_id)
```

Update `templates/contacts/form.html` company dropdown to check `preselect_company_id`:
```html
<option value="{{ c.id }}" {% if (contact and contact.company_id == c.id) or (preselect_company_id and preselect_company_id == c.id) %}selected{% endif %}>
```

### List page update: `companies/list.html`

Change company names from plain text to clickable links:

```html
<!-- Before -->
<div class="font-medium text-gray-900">{{ company.name }}</div>

<!-- After -->
<a href="{{ url_for('companies.view_company', id=company.id) }}" class="font-medium text-gray-900 hover:text-primary-600">{{ company.name }}</a>
```

### Edge Cases

- **Company with zero contacts**: Show empty state with "Add Contact" CTA linking to `/contacts/new?company_id=<id>`
- **Contact with no email**: Display "-"
- **Contact with no last_contact_date**: Display "-"
- **Website without protocol**: Prepend `https://` before rendering as `<a>` tag
- **Website is null/empty**: Hide the website element entirely
- **Contacts from other companies**: Only contacts with matching `company_id` are loaded via the relationship — no risk of cross-company leakage

### What This Does NOT Include

- No new models or migrations
- No inventory list on the company page (future work)
- No deals/pipeline display (future work)
- No inline contact editing from the company page
- No delete button on detail page (stays on list page only)
- No pagination on contacts table (companies won't have hundreds of contacts in this domain)

## Implementation Steps

1. Add `view_company` route to `routes/companies.py` with `joinedload` for contacts
2. Create `templates/companies/view.html` with company info cards + contacts table
3. Update `templates/companies/list.html` to link company names to detail page
4. Update `edit_company` redirect to go to detail page instead of list
5. Add `?company_id=` pre-fill support to `routes/contacts.py` and `templates/contacts/form.html`
6. Add tests for the new route
7. Run Playwright E2E test to verify page loads and contacts display

## Testing

- **Unit test**: Route returns 200, template renders with correct contacts (not contacts from other companies)
- **Edge case**: Company with zero contacts renders empty state
- **Edge case**: Company 404 returns proper error
- **E2E**: Navigate from list → detail → verify contacts visible → click Edit → save → verify redirect back to detail page
