# Codebase Map - Mouse Domination

> **Last Updated:** 2026-01-18
> **Purpose:** Quick context for AI assistants. Reduces exploration time and token usage.

## Overview

**Mouse Domination** is a creator management SaaS platform built with Flask. It handles:
- Multi-podcast production with role-based access
- Inventory management (review units, purchases)
- Affiliate revenue tracking
- Sales pipeline & deal management
- Community collaborations
- AI content repurposing (Content Atomizer)
- Social media posting

**Scale:** ~7,100 lines routes, ~1,900 lines models, ~5,200 lines services/utils

---

## Directory Structure

```
mouse_domination/
├── app.py                 # App factory, blueprint registration, security headers
├── config.py              # Dev/Prod/Test configurations
├── constants.py           # Centralized enums and choices
├── extensions.py          # Flask extensions (db, csrf, login, limiter)
├── models.py              # 29 database models (~1,900 lines)
│
├── routes/                # 17 blueprints (~7,100 lines)
│   ├── main.py            # Dashboard, health checks
│   ├── auth.py            # Login, signup, 2FA, password reset
│   ├── admin.py           # User approval, audit logs
│   ├── podcasts.py        # Multi-podcast hub + episodes (~1,900 lines)
│   ├── inventory.py       # Product inventory
│   ├── pipeline.py        # Sales deals
│   ├── affiliates.py      # Revenue tracking
│   ├── collabs.py         # Collaborations
│   ├── contacts.py        # Contact CRUD
│   ├── companies.py       # Company/brand CRUD
│   ├── calendar.py        # Event scheduling
│   ├── revenue.py         # Revenue dashboards
│   ├── content_atomizer.py # AI content generation
│   ├── social.py          # Social media integration
│   ├── media_kit.py       # Creator profile
│   ├── settings.py        # User preferences, 2FA setup
│   └── templates.py       # Outreach templates
│
├── services/              # Business logic layer
│   ├── base.py            # Base service, CRUD patterns, error handling
│   ├── content_atomizer.py # OpenAI/Anthropic integration
│   ├── social_posting.py  # Multi-platform posting
│   ├── discord.py         # Discord bot integration
│   └── options.py         # Dynamic custom options
│
├── utils/                 # Utilities
│   ├── podcast_access.py  # Multi-podcast access control
│   ├── validation.py      # Input validation
│   ├── routes.py          # Form error handling
│   └── logging.py         # Structured logging
│
├── templates/             # Jinja2 templates (68 files, 21 subdirs)
│   ├── base.html          # Master layout (Tailwind + Alpine.js)
│   └── [feature]/         # Per-feature: list.html, form.html, _table.html
│
├── tests/                 # Test suite (27 files, 878 tests)
│   └── conftest.py        # Fixtures
│
├── migrations/versions/   # Alembic migrations
├── docs/                  # PRDs, ADRs, patterns guide
└── scripts/               # Deploy, backup, migration scripts
```

---

## Key Models

### User-Scoped (filter by `current_user.id`)
| Model | Purpose | Key Fields |
|-------|---------|------------|
| `Inventory` | Products for review | `product_name`, `status`, `deadline`, `company_id` |
| `AffiliateRevenue` | Revenue tracking | `company_id`, `amount`, `date`, `platform` |
| `SalesPipeline` | Deals & negotiation | `company_id`, `status`, `amount`, `deal_type` |
| `Collaboration` | Creator collabs | `contact_id`, `collab_type`, `status` |

### Shared (no user filter)
| Model | Purpose | Key Fields |
|-------|---------|------------|
| `Company` | Brands/companies | `name`, `affiliate_status`, `relationship_status` |
| `Contact` | People at companies | `name`, `role`, `company_id`, `relationship_status` |

### Multi-Podcast
| Model | Purpose | Key Fields |
|-------|---------|------------|
| `Podcast` | Podcast shows | `name`, `slug`, `created_by` |
| `PodcastMember` | Access control | `podcast_id`, `user_id`, `role` (owner/editor/viewer) |
| `EpisodeGuide` | Episode content | `podcast_id`, `title`, `status`, `scheduled_date` |
| `EpisodeGuideItem` | Episode sections | `guide_id`, `section_key`, `content` |
| `EpisodeGuideTemplate` | Reusable templates | `podcast_id`, `name`, `default_sections` |

### Supporting
| Model | Purpose |
|-------|---------|
| `DealDeliverable` | Deliverables per deal |
| `ContentAtomicTemplate` | AI prompt templates |
| `ContentAtomicSnippet` | Generated snippets |
| `DiscordIntegration` | Discord config per template |
| `CustomOption` | User-extensible choices |

---

## Route Patterns

### Blueprint Registration (app.py)
```python
# All blueprints registered with URL prefixes
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(podcasts_bp, url_prefix='/podcasts')
# ... 15 more blueprints
```

### URL Structure
| Prefix | Blueprint | Purpose |
|--------|-----------|---------|
| `/` | main | Dashboard |
| `/auth` | auth | Authentication |
| `/admin` | admin | Admin panel |
| `/podcasts` | podcasts | Podcast management + episodes |
| `/inventory` | inventory | Product inventory |
| `/pipeline` | pipeline | Sales pipeline |
| `/affiliates` | affiliates | Affiliate revenue |
| `/collabs` | collabs | Collaborations |
| `/contacts` | contacts | Contacts |
| `/companies` | companies | Companies |
| `/calendar` | calendar | Calendar |
| `/revenue` | revenue | Revenue dashboards |
| `/atomizer` | content_atomizer | AI content |
| `/social` | social | Social posting |
| `/settings` | settings | User settings |
| `/media-kit` | media_kit | Creator profile |
| `/templates` | templates | Outreach templates |

### Common Route Pattern
```python
@blueprint.route('/')
@login_required
def list_items():
    query = Model.query.filter_by(user_id=current_user.id)  # User scoping
    query = query.options(joinedload(Model.relation))       # Eager load
    items = query.paginate(page=page, per_page=20)          # Pagination

    if request.args.get('ajax') == '1':                     # AJAX support
        return render_template('module/_table.html', items=items)
    return render_template('module/list.html', items=items)
```

---

## Architecture Patterns

### Multi-Podcast Access Control
```python
# Decorator for podcast routes
@require_podcast_access
def podcast_view(podcast_id):
    # Checks PodcastMember table for user access
    pass

# Helper functions (utils/podcast_access.py)
get_user_podcasts(user)              # Get all podcasts user can access
user_has_podcast_access(user, pod)   # Check specific access
get_user_role_for_podcast(user, pod) # Get role (owner/editor/viewer)
```

### Service Layer
```python
routes/ → services/ → models.py → db
         ↑
    Business logic, external APIs
```

### Error Handling
```python
# services/base.py
class ServiceError(Exception): pass
class NotFoundError(ServiceError): pass
class ValidationError(ServiceError): pass

# @db_transaction decorator handles rollbacks
```

### AJAX Live Search
1. User types → Alpine.js captures
2. Fetch `?ajax=1` → Server returns `_table.html` partial
3. JavaScript replaces results container
4. No full page reload

---

## Security Architecture

| Layer | Implementation |
|-------|---------------|
| **Auth** | Flask-Login + Argon2id hashing |
| **2FA** | PyOTP TOTP + recovery codes |
| **Sessions** | 2-hour timeout, HttpOnly, Secure |
| **CSRF** | WTForms CSRFProtect |
| **Rate Limit** | Flask-Limiter (5/min auth) |
| **Headers** | X-Frame-Options, CSP, etc. |

---

## Testing

```bash
pytest                    # Run all (878 tests)
pytest tests/test_auth.py # Run specific file
pytest -k "test_login"    # Run by name pattern
pytest --tb=short         # Short tracebacks
```

**Key fixtures (conftest.py):**
- `app` - Test app with in-memory DB
- `client` - Test client
- `auth_client` - Logged-in client
- `test_user` - Sample user dict
- `test_podcast` - Podcast + membership

---

## Development

```bash
# Start database
docker compose -f deploy/docker-compose.dev.yml up -d

# Run dev server
source .venv/bin/activate
flask run --port 5001
# → http://127.0.0.1:5001

# DB migrations
flask db migrate -m "Add field"
flask db upgrade
```

---

## Production

- **Server:** Hetzner 178.156.211.75
- **Deploy:** Push to `main` → GitHub Actions → auto-deploy
- **App:** `/opt/apps/mouse_domination`
- **Logs:** `docker compose logs -f mouse-domination`

---

## Quick Reference

### Adding a New Feature
1. Add model(s) to `models.py`
2. Create migration: `flask db migrate -m "..."`
3. Add blueprint to `routes/`
4. Register in `app.py`
5. Create templates in `templates/feature/`
6. Add tests in `tests/test_feature.py`

### User-Scoped Query
```python
items = Model.query.filter_by(user_id=current_user.id).all()
```

### Podcast-Scoped Query
```python
episodes = EpisodeGuide.query.filter_by(podcast_id=podcast.id).all()
```

### Eager Loading (N+1 prevention)
```python
from sqlalchemy.orm import joinedload
query = Model.query.options(joinedload(Model.company))
```

---

## Recent Changes

| Date | Change |
|------|--------|
| 2026-01-18 | Consolidated episode_guide routes into podcasts blueprint |
| 2026-01-18 | Added episode_url field to EpisodeGuide |
| 2026-01-xx | Added Creator Hub Phase 1-3 (Revenue, Atomizer, Social) |
| 2026-01-xx | Added multi-podcast ownership with role-based access |
