# Comprehensive Code Review Report

**Date:** 2026-01-12
**Codebase:** Mouse Domination
**Size:** ~12,000 lines Python, 69 HTML templates

---

## Executive Summary

| Category | Status | Key Finding |
|----------|--------|-------------|
| **Security** | Good | No critical vulnerabilities. 3 medium issues. |
| **Code Quality** | Needs Work | 300-400 lines of redundant CRUD code |
| **Performance** | Fair | N+1 query risks, missing indexes |
| **Templates** | Needs Work | No form macros, repeated styling |

**Overall Assessment:** The codebase has solid fundamentals (good auth, CSRF protection, validation utilities) but has accumulated technical debt in the form of repetitive CRUD patterns that weren't abstracted.

---

## 1. Security Findings

### No Critical/High Issues Found

### Medium Severity (3)

| Issue | Location | Fix |
|-------|----------|-----|
| Information disclosure in health check | `routes/main.py:23-29` | Replace `str(e)` with generic message |
| Potential XSS in template preview | `templates/outreach/preview.html:44,50` | Review if HTML formatting intended |
| CSRF on AJAX endpoints | `routes/episode_guide.py:314+` | Verify X-CSRFToken header checked |

### Low Severity (5)

| Issue | Location | Fix |
|-------|----------|-----|
| No user scoping on shared resources | All CRUD routes | Intentional for shared use - document |
| LIKE wildcards not escaped | Search filters | Escape `%` and `_` in search input |
| Session config enhancements | `config.py` | Add session lifetime limit |

### Positive Security Findings
- Argon2id password hashing with OWASP parameters
- Rate limiting and account lockout
- CSRF protection globally enabled
- Security headers configured
- No SQL injection (all queries parameterized)
- No hardcoded secrets

---

## 2. Code Redundancy (Routes)

### Summary: ~300-400 lines can be eliminated

### 2.1 Delete Routes (7 copies, ~90 lines redundant)

Every route file has identical delete pattern:

```python
@bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete_entity(id):
    try:
        entity = Model.query.get_or_404(id)
        name = entity.name
        db.session.delete(entity)
        db.session.commit()
        flash(f'Entity "{name}" deleted.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash('Database error occurred.', 'error')
    return redirect(url_for('module.list'))
```

**Files:** contacts.py, companies.py, affiliates.py, collabs.py, pipeline.py, inventory.py, templates.py

**Recommendation:** Create `make_delete_view()` factory function.

### 2.2 Try-Except Blocks (14 routes, ~150 lines redundant)

Every create/edit route has duplicate exception handling:

```python
except ValidationError as e:
    flash(f'{e.field}: {e.message}', 'error')
    return render_template(...)  # Re-fetches dropdown data
except SQLAlchemyError as e:
    db.session.rollback()
    flash('Database error occurred.', 'error')
    return render_template(...)  # Re-fetches dropdown data AGAIN
```

**Critical:** The `handle_form_errors` decorator exists in `utils/routes.py:21-53` but is **NOT USED ANYWHERE**.

**Recommendation:** Restructure routes to use existing decorator.

### 2.3 Dropdown Data Fetched 3x Per Route (~50 lines)

Form context data fetched in: (1) GET handler, (2) ValidationError handler, (3) SQLAlchemyError handler.

**Recommendation:** Fetch once at route start, reuse in all branches.

### 2.4 Inconsistent Validation

| Pattern | Files Using |
|---------|-------------|
| `FormData` class (good) | contacts, collabs, pipeline, inventory, templates, episode_guide |
| Manual `request.form.get()` (verbose) | companies, affiliates |

**Recommendation:** Convert companies.py and affiliates.py to use `FormData`.

### 2.5 Quick Actions (3 files, ~30 lines redundant)

`complete_collab()`, `mark_sold()`, `mark_complete()` all follow same pattern.

**Recommendation:** Create `@quick_action` decorator.

---

## 3. Model/Database Issues

### 3.1 Missing Indexes

| Column | Model | Query Pattern |
|--------|-------|---------------|
| `category` | Company | Filtered in list views |
| `affiliate_status` | Company | Filtered in affiliate routes |
| `status` | Collaboration, SalesPipeline | Filtered frequently |

**Recommendation:** Add `index=True` to these columns.

### 3.2 N+1 Query Risks

| Location | Issue | Fix |
|----------|-------|-----|
| `EpisodeGuide.items` access | Routes load guide, then access items | Use `joinedload(EpisodeGuide.items)` |
| `to_dict()` methods | Access relationships without preload | Ensure joinedload before serialization |
| `EpisodeGuideTemplate.guides.count()` | COUNT query per template in list | Pass count from service layer |

### 3.3 Data Type Issues

| Column | Current | Recommended |
|--------|---------|-------------|
| `cost`, `sale_price`, `revenue`, `rate_quoted` | `Float` | `Numeric(10, 2)` for currency precision |
| `link` column on EpisodeGuideItem | Redundant with `links` JSON | Migrate and drop legacy column |

### 3.4 Dropdown Queries Load Full Objects

`utils/queries.py:14,25` - Dropdowns only need `id` and `name` but load all columns.

**Recommendation:** Use `load_only(Model.id, Model.name)`.

---

## 4. Template Redundancy

### 4.1 No Form Field Macros

Only `macros.html` for pagination exists. Form fields repeat styling across 8 form templates:

```html
class="w-full border border-surface-200 rounded-lg px-3 py-2 text-sm
       focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
```

**Recommendation:** Create form macros:
```jinja
{% macro text_input(name, label, value='', required=false) %}
<div>
    <label class="block text-sm font-medium text-gray-700 mb-1">{{ label }}{% if required %} *{% endif %}</label>
    <input type="text" name="{{ name }}" value="{{ value }}"
           {% if required %}required{% endif %}
           class="w-full border border-surface-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500">
</div>
{% endmacro %}
```

### 4.2 Repeated List Table Structure

All list templates have similar table structures with status badges, action buttons, etc.

**Future:** Consider table component macro.

---

## 5. Prioritized Recommendations

### Immediate (Do Before New Features)

| Priority | Task | Effort | Impact |
|----------|------|--------|--------|
| 1 | Fix health check info disclosure | 5 min | Security |
| 2 | Add missing indexes (category, affiliate_status) | 15 min | Performance |
| 3 | Fix N+1 on episode guide items | 30 min | Performance |

### Short-Term (Next Sprint)

| Priority | Task | Effort | Impact |
|----------|------|--------|--------|
| 4 | Create generic delete view factory | 1 hr | -90 lines |
| 5 | Use `handle_form_errors` decorator | 2 hr | -150 lines |
| 6 | Convert companies/affiliates to FormData | 1 hr | Consistency |
| 7 | Create form field macros | 2 hr | Template DRY |

### Medium-Term (Tech Debt Sprint)

| Priority | Task | Effort | Impact |
|----------|------|--------|--------|
| 8 | Migrate Float to Numeric for currency | 1 hr | Data integrity |
| 9 | Remove legacy `link` column | 30 min | Schema cleanup |
| 10 | Add `load_only` to dropdown queries | 30 min | Memory |
| 11 | Create quick action decorator | 1 hr | -30 lines |

---

## 6. Code Metrics

```
Python Files:     50
Python Lines:     12,183
HTML Templates:   69
Test Files:       16
Test Coverage:    Good (520+ tests)

Routes:           12 blueprint files
Models:           11 SQLAlchemy models
Services:         4 service classes (underutilized)
Utils:            5 utility modules
```

### Duplication Estimate

| Category | Lines | Potential Savings |
|----------|-------|-------------------|
| Route CRUD patterns | ~1,450 | 300-400 (20-27%) |
| Template forms | ~800 | 100-150 (12-18%) |
| **Total** | ~2,250 | ~400-550 |

---

## 7. Architecture Notes

### Good Patterns Already Present
- Blueprint organization
- Service layer (partially adopted)
- FormData validation helper
- Request-scoped dropdown caching
- Centralized error handling decorator (unused!)

### Patterns to Adopt More Fully
- Use existing `handle_form_errors` decorator
- Use existing service classes for complex queries
- Add form macros to templates

---

## Appendix: Files to Modify

### Security Fixes
- `routes/main.py:23-29` - Health check error message

### Index Additions
- `models.py:159` - Company.category
- `models.py:162` - Company.affiliate_status

### N+1 Fixes
- `routes/episode_guide.py` - Add joinedload for items queries

### Refactoring Targets
- `routes/contacts.py` - Apply delete factory, form decorator
- `routes/companies.py` - Convert to FormData, apply patterns
- `routes/affiliates.py` - Convert to FormData, apply patterns
- `routes/collabs.py` - Apply delete factory, form decorator
- `routes/pipeline.py` - Apply delete factory, form decorator
- `routes/inventory.py` - Apply delete factory, form decorator
- `routes/templates.py` - Apply delete factory, form decorator
- `templates/macros.html` - Add form field macros
