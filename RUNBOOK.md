# Mouse Domination Runbook

A comprehensive reference for operating, developing, and troubleshooting the Mouse Domination CRM application.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Current Deployment](#current-deployment)
3. [Authentication System](#authentication-system)
4. [Database Schema](#database-schema)
5. [Key Files Reference](#key-files-reference)
6. [Common Operations](#common-operations)
7. [Development Workflow](#development-workflow)
8. [Troubleshooting](#troubleshooting)
9. [Security Considerations](#security-considerations)

---

## Architecture Overview

### Stack

```
┌─────────────────────────────────────────────────────────────┐
│                        Internet                              │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              Cloudflare Tunnel (HTTPS)                       │
│              app.dazztrazak.com → localhost:8000            │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              Gunicorn (WSGI Server)                          │
│              127.0.0.1:8000, 2 workers                       │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              Flask Application                               │
│              ┌─────────────────────────────────────────┐    │
│              │  Flask-Login (Sessions)                 │    │
│              │  Flask-WTF (CSRF Protection)            │    │
│              │  Flask-Limiter (Rate Limiting)          │    │
│              │  SQLAlchemy (ORM)                       │    │
│              └─────────────────────────────────────────┘    │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              SQLite Database                                 │
│              mouse_domination.db                             │
└─────────────────────────────────────────────────────────────┘
```

### Request Flow

1. User requests `https://app.dazztrazak.com/inventory`
2. Cloudflare Tunnel forwards to `localhost:8000`
3. Gunicorn receives request, passes to Flask app
4. Flask-Login checks session cookie for authentication
5. If not authenticated → redirect to `/auth/login`
6. If authenticated → route handler processes request
7. SQLAlchemy queries database, filtered by `user_id`
8. Jinja2 renders template with TailwindCSS
9. Response returned through the stack

---

## Current Deployment

### Host Machine

- **Location**: Austin's MacBook (local machine)
- **Directory**: `/Users/austin/Git_Repos/mouse_domination`
- **Python**: 3.14 (in `.venv`)
- **Domain**: `app.dazztrazak.com`

### Running Services

| Service | Port | Command |
|---------|------|---------|
| Gunicorn | 8000 | `gunicorn "app:create_app()" --bind 127.0.0.1:8000 --workers 2 --daemon` |
| Cloudflare Tunnel | - | Runs as system service, routes to 8000 |
| Flask Dev Server | 5001 | `flask run --port 5001` (development only) |

### Key Files on Disk

```
/Users/austin/Git_Repos/mouse_domination/
├── .env                    # Environment variables (SECRET_KEY, etc.)
├── mouse_domination.db     # SQLite database (ALL DATA)
├── backups/                # Database backups
└── .venv/                  # Python virtual environment
```

### Starting/Stopping the App

```bash
# Restart production (gunicorn)
./deploy.sh

# Or manually:
pkill -f gunicorn
source .venv/bin/activate
gunicorn "app:create_app()" --bind 127.0.0.1:8000 --workers 2 --daemon

# Check if running
pgrep -f gunicorn

# View gunicorn logs (if not daemonized)
# Logs go to stderr when running in foreground
```

---

## Authentication System

### Overview

Replaced Cloudflare Access (Jan 2026) with native Flask-Login due to slow OTP emails (30+ min delays).

### Components

| Component | Purpose |
|-----------|---------|
| Flask-Login | Session management, `@login_required` decorator |
| Argon2id | Password hashing (OWASP recommended) |
| Flask-Limiter | Rate limiting on login (5/min) |
| CSRF Protection | Flask-WTF on all forms |

### User Model Fields

```python
# models.py - User class
id                    # Primary key
email                 # Unique, used for login
name                  # Optional display name
password_hash         # Argon2id hash
is_approved           # Must be True to log in
is_admin              # Can access /admin/users
failed_login_attempts # Tracks failed logins
locked_until          # Account lockout timestamp
last_login_at         # Last successful login
created_at            # Registration timestamp
```

### Authentication Flow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Register   │────▶│   Pending    │────▶│   Approved   │
│  /auth/reg   │     │  is_approved │     │  Can login   │
│              │     │   = False    │     │              │
└──────────────┘     └──────────────┘     └──────────────┘
                            │
                            ▼
                     Admin approves at
                     /admin/users
```

### Login Security

1. **Rate Limiting**: 5 attempts per minute per IP
2. **Progressive Lockout**:
   - 5 failures → 5 min lock
   - 6 failures → 15 min lock
   - 7 failures → 1 hour lock
   - 8+ failures → 24 hour lock
3. **Timing-Safe**: Always hashes something to prevent user enumeration
4. **Session Protection**: `strong` mode regenerates session on login

### Password Requirements

- Minimum 12 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one digit
- At least one special character (`!@#$%^&*()_+-=[]{}|;:,.<>?`)

### Admin Functions

Located at `/admin/users` (requires `is_admin=True`):
- View pending registrations
- Approve/reject users
- Grant/revoke admin privileges
- Remove users

---

## Database Schema

### Entity Relationship

```
User (1) ─────────< (N) Inventory
  │
  └──────────────< (N) AffiliateRevenue
  │
  └──────────────< (N) Collaboration
  │
  └──────────────< (N) PipelineDeal

Company (1) ──────< (N) Contact
  │
  └──────────────< (N) Inventory
  │
  └──────────────< (N) Collaboration
  │
  └──────────────< (N) PipelineDeal

EpisodeGuide (standalone, not user-scoped)
OutreachTemplate (standalone, not user-scoped)
```

### Key Tables

| Table | Purpose | User-Scoped? |
|-------|---------|--------------|
| users | Authentication & user data | N/A |
| inventory | Review units, purchases, sales | Yes |
| companies | Brand/company records | No (shared) |
| contacts | Brand contacts | No (shared) |
| collaborations | Brand deals/collabs | Yes |
| pipeline_deals | Sponsorship pipeline | Yes |
| affiliate_revenue | Monthly affiliate income | Yes |
| episode_guides | Podcast episode planning | No (shared) |
| outreach_templates | Email templates | No (shared) |

### Multi-User Data Isolation

User-scoped tables have a `user_id` foreign key. All queries filter by `current_user.id`:

```python
# Example from routes/inventory.py
Inventory.query.filter_by(user_id=current_user.id)
```

---

## Key Files Reference

### Application Core

| File | Purpose |
|------|---------|
| `app.py` | Application factory, blueprint registration |
| `config.py` | Configuration classes (Dev, Prod, Test) |
| `extensions.py` | Flask extensions (db, csrf, login_manager, limiter) |
| `models.py` | SQLAlchemy models |
| `constants.py` | Dropdown choices, status values |

### Routes (Blueprints)

| File | URL Prefix | Purpose |
|------|------------|---------|
| `routes/auth.py` | `/auth` | Login, logout, register |
| `routes/admin.py` | `/admin` | User management |
| `routes/main.py` | `/` | Dashboard, health check |
| `routes/inventory.py` | `/inventory` | Inventory CRUD |
| `routes/contacts.py` | `/contacts` | Contact management |
| `routes/companies.py` | `/companies` | Company management |
| `routes/affiliates.py` | `/affiliates` | Revenue tracking |
| `routes/collabs.py` | `/collabs` | Collaborations |
| `routes/pipeline.py` | `/pipeline` | Sponsorship deals |
| `routes/templates.py` | `/templates` | Outreach templates |
| `routes/episode_guide.py` | `/guide` | MouseCast episodes |

### Templates

| Directory | Purpose |
|-----------|---------|
| `templates/base.html` | Base layout, navigation |
| `templates/dashboard.html` | Main dashboard |
| `templates/auth/` | Login, register, pending |
| `templates/admin/` | User management |
| `templates/inventory/` | Inventory list, form |
| `templates/episode_guide/` | Episode list, form, view |

### Utilities

| File | Purpose |
|------|---------|
| `utils/validation.py` | Form validation helpers |
| `utils/routes.py` | FormData class for form processing |
| `utils/logging.py` | Logging configuration |
| `utils/queries.py` | Common database queries |

### Scripts

| File | Purpose |
|------|---------|
| `deploy.sh` | Restart gunicorn |
| `scripts/backup_db.sh` | SQLite backup |
| `scripts/migrate_flask_login.py` | Auth migration + admin setup |

---

## Common Operations

### Restart the Application

```bash
./deploy.sh
```

### Create Database Backup

```bash
./scripts/backup_db.sh
# Backup saved to: backups/mouse_domination_YYYYMMDD_HHMMSS.db
```

### Add a New Admin User

```bash
source .venv/bin/activate
python3 << 'EOF'
from app import create_app, db
from models import User

app = create_app()
with app.app_context():
    user = User.query.filter_by(email='newemail@example.com').first()
    if user:
        user.is_admin = True
        user.is_approved = True
        db.session.commit()
        print(f"Made {user.email} an admin")
    else:
        print("User not found")
EOF
```

### Reset a User's Password

```bash
source .venv/bin/activate
python3 << 'EOF'
from app import create_app, db
from models import User

app = create_app()
with app.app_context():
    user = User.query.filter_by(email='user@example.com').first()
    if user:
        user.set_password('NewSecurePassword123!')
        user.failed_login_attempts = 0
        user.locked_until = None
        db.session.commit()
        print(f"Password reset for {user.email}")
EOF
```

### Unlock a Locked Account

```bash
source .venv/bin/activate
python3 << 'EOF'
from app import create_app, db
from models import User

app = create_app()
with app.app_context():
    user = User.query.filter_by(email='user@example.com').first()
    if user:
        user.failed_login_attempts = 0
        user.locked_until = None
        db.session.commit()
        print(f"Account unlocked: {user.email}")
EOF
```

### Check Application Health

```bash
curl http://127.0.0.1:8000/health
# Should return: {"status": "healthy"}
```

### View All Users

```bash
source .venv/bin/activate
python3 << 'EOF'
from app import create_app
from models import User

app = create_app()
with app.app_context():
    for u in User.query.all():
        print(f"{u.email} | admin={u.is_admin} | approved={u.is_approved}")
EOF
```

---

## Development Workflow

### Setup

```bash
cd /Users/austin/Git_Repos/mouse_domination
source .venv/bin/activate
```

### Run Development Server

```bash
flask run --port 5001 --debug
# Access at http://localhost:5001
# Auto-reloads on code changes
```

### Code Changes → Production

Changes to Python files are automatically picked up by gunicorn (if it's watching) or require a restart:

```bash
./deploy.sh
```

### Adding a New Route

1. Create/edit file in `routes/`
2. Add `@login_required` decorator
3. Register blueprint in `app.py` if new file
4. Create templates in `templates/`

### Adding a New Model Field

1. Add field to model in `models.py`
2. Create migration script in `scripts/`
3. Run migration: `python scripts/migrate_xyz.py`

---

## Troubleshooting

### CSRF Token Missing Error

**Symptom**: "Bad Request - The CSRF session token is missing"

**Causes**:
1. `SECRET_KEY` not set or changed → sessions invalidated
2. Cookies blocked/cleared between GET and POST

**Fix**:
```bash
# Ensure .env has SECRET_KEY
cat .env | grep SECRET_KEY

# If missing, generate and add:
python -c "import secrets; print(secrets.token_hex(32))"
# Add to .env: SECRET_KEY=<generated_key>

# Restart app
./deploy.sh

# Clear browser cookies and try again
```

### Login Redirects Back to Login

**Symptom**: After logging in, clicking any link redirects back to login

**Causes**:
1. Session cookie not being set (check browser dev tools)
2. `is_approved=False` on user account
3. Session protection blocking the session

**Fix**:
```bash
# Check user status
source .venv/bin/activate
python3 -c "
from app import create_app
from models import User
app = create_app()
with app.app_context():
    u = User.query.filter_by(email='your@email.com').first()
    print(f'approved={u.is_approved}, admin={u.is_admin}')
"
```

### Account Locked

**Symptom**: "Account locked. Try again in X minutes."

**Fix**: See [Unlock a Locked Account](#unlock-a-locked-account) above.

### Gunicorn Not Starting

**Symptom**: `./deploy.sh` fails, health check returns 000

**Debug**:
```bash
# Run gunicorn in foreground to see errors
source .venv/bin/activate
gunicorn "app:create_app()" --bind 127.0.0.1:8000 --workers 1

# Check for port conflicts
lsof -i:8000
```

### Database Errors

**Symptom**: "no such column" or similar SQLite errors

**Fix**:
```bash
# Backup first!
./scripts/backup_db.sh

# Check if migration script exists for the issue
ls scripts/migrate_*.py

# Or manually add column
source .venv/bin/activate
python3 << 'EOF'
from app import create_app, db
app = create_app()
with app.app_context():
    db.engine.execute('ALTER TABLE tablename ADD COLUMN newcol TEXT')
EOF
```

---

## Security Considerations

### Sensitive Files

| File | Contains | Git Status |
|------|----------|------------|
| `.env` | SECRET_KEY, credentials | .gitignored |
| `mouse_domination.db` | All user data | .gitignored |
| `backups/` | Database backups | .gitignored |

### OWASP Top 10 Mitigations

| Risk | Mitigation |
|------|------------|
| A01 Broken Access | `@login_required` on all routes, `user_id` filtering |
| A02 Crypto Failures | Argon2id hashing, HTTPS via Cloudflare |
| A03 Injection | SQLAlchemy ORM (parameterized queries) |
| A04 Insecure Design | Rate limiting, account lockout |
| A05 Security Misconfig | Environment-based config, no debug in prod |
| A07 Auth Failures | Strong passwords, session protection |
| A08 Integrity | CSRF tokens on all forms |

### Password Hashing Details

```python
# Argon2id parameters (models.py)
PasswordHasher(
    time_cost=3,        # Iterations
    memory_cost=65536,  # 64MB memory
    parallelism=4       # Threads
)
```

### Session Configuration

```python
# config.py
SESSION_COOKIE_SECURE = True      # HTTPS only (production)
SESSION_COOKIE_HTTPONLY = True    # No JavaScript access
SESSION_COOKIE_SAMESITE = 'Lax'   # CSRF protection
```

---

## Quick Reference for Claude Code Sessions

### Context Loading

When starting a new Claude Code session on this project:

1. **Read this file first** (`RUNBOOK.md`)
2. **Check current state**:
   ```bash
   git status
   pgrep -f gunicorn && echo "App running" || echo "App stopped"
   ```
3. **Key architectural decisions**:
   - Flask-Login for auth (replaced Cloudflare Access Jan 2026)
   - SQLite database (single file, no migrations framework)
   - Self-hosted on Austin's MacBook via Cloudflare Tunnel
   - Multi-user with admin approval workflow

### Common Tasks for AI Assistants

| Task | Key Files |
|------|-----------|
| Add new feature | `routes/*.py`, `templates/*/`, `models.py` |
| Fix auth issue | `routes/auth.py`, `models.py` (User class) |
| Update UI | `templates/base.html`, `templates/*/` |
| Database changes | `models.py`, `scripts/migrate_*.py` |
| Deployment issues | `deploy.sh`, `.env`, check gunicorn |

### Don't Forget

- All routes need `@login_required` (except `/auth/*`, `/health`)
- User-scoped data must filter by `current_user.id`
- Test on `localhost:5001` before deploying
- Run `./deploy.sh` to push changes to production
- CSRF tokens required on all POST forms

---

*Last updated: January 2026*
