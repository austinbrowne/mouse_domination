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

### Production Stack

```
┌─────────────────────────────────────────────────────────────┐
│                        Internet                              │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              Cloudflare Tunnel (HTTPS)                       │
│              app.dazztrazak.com → Docker container          │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              Docker (Hetzner Server)                         │
│              Gunicorn WSGI Server                            │
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
│              PostgreSQL Database                             │
│              Docker container                                │
└─────────────────────────────────────────────────────────────┘
```

### Local Development Stack

```
┌─────────────────────────────────────────────────────────────┐
│              Flask Development Server                        │
│              http://127.0.0.1:5001                           │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              PostgreSQL (Docker)                             │
│              localhost:5433                                  │
└─────────────────────────────────────────────────────────────┘
```

### Request Flow (Production)

1. User requests `https://app.dazztrazak.com/inventory`
2. Cloudflare Tunnel forwards to Docker container on Hetzner
3. Gunicorn receives request, passes to Flask app
4. Flask-Login checks session cookie for authentication
5. If not authenticated → redirect to `/auth/login`
6. If authenticated → route handler processes request
7. SQLAlchemy queries PostgreSQL, filtered by `user_id`
8. Jinja2 renders template with TailwindCSS
9. Response returned through the stack

---

## Current Deployment

### Production (Remote)

- **Server**: Hetzner (178.156.211.75), user `austin`
- **Stack**: Docker Compose at `/opt/apps/infra/docker-compose.yml`
- **Domain**: `app.dazztrazak.com` (via Cloudflare Tunnel)
- **Database**: PostgreSQL in Docker container

### Local Development

- **Directory**: `/Users/austin/Git_Repos/mouse_domination`
- **Python**: 3.14 (in `.venv`)
- **URL**: http://127.0.0.1:5001
- **Database**: PostgreSQL via `docker-compose.dev.yml` (port 5433)

### Running Services

| Environment | Service | Port | Command |
|-------------|---------|------|---------|
| Local | Flask Dev Server | 5001 | `flask run --port 5001` |
| Local | PostgreSQL | 5433 | `docker compose -f docker-compose.dev.yml up -d` |
| Production | Docker/Gunicorn | 5000 | Managed by Docker Compose |
| Production | PostgreSQL | 5432 | Managed by Docker Compose |

### Key Files on Disk (Local)

```
/Users/austin/Git_Repos/mouse_domination/
├── .env                    # Environment variables (SECRET_KEY, DATABASE_URL)
├── backups/                # Database backups
└── .venv/                  # Python virtual environment
```

### Starting/Stopping the App

**Local Development:**
```bash
# Start PostgreSQL (if not running)
docker compose -f docker-compose.dev.yml up -d

# Start Flask dev server
source .venv/bin/activate
flask run --port 5001

# Or with debug mode
FLASK_ENV=development flask run --port 5001

# Check if running
curl http://127.0.0.1:5001/health
```

**Production (Remote):**
```bash
ssh austin@178.156.211.75
cd /opt/apps/infra
docker compose logs -f mouse-domination  # View logs
docker compose restart mouse-domination  # Restart app
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
| `scripts/backup_db.sh` | Database backup (legacy SQLite) |
| `scripts/migrate_flask_login.py` | Auth migration + admin setup |
| `scripts/sync_from_production.py` | Sync data from production to local |

---

## Common Operations

### Restart the Application

**Local:**
```bash
# Flask dev server auto-reloads, or manually:
pkill -f "flask run.*5001"
flask run --port 5001
```

**Production:**
```bash
ssh austin@178.156.211.75
cd /opt/apps/infra
docker compose restart mouse-domination
```

### Create Database Backup

**Local (PostgreSQL):**
```bash
docker compose -f docker-compose.dev.yml exec db pg_dump -U mouse mouse_domination > backup.sql
```

**Production:**
```bash
ssh austin@178.156.211.75
cd /opt/apps/infra
docker compose exec db pg_dump -U mousedom mousedom > backup_$(date +%Y%m%d).sql
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
# Local
curl http://127.0.0.1:5001/health

# Production
curl https://app.dazztrazak.com/health
# Should return: {"status": "healthy", "database": "connected", ...}
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

# Start local PostgreSQL (first time or after reboot)
docker compose -f docker-compose.dev.yml up -d
```

### Run Development Server

```bash
flask run --port 5001
# Access at http://127.0.0.1:5001
# Auto-reloads on code changes
```

### Code Changes → Production

Push to `main` branch triggers GitHub Actions CI/CD:
1. Pulls latest code to Hetzner server
2. Rebuilds and restarts Docker container
3. Runs migrations if `migrations/` folder changed

```bash
git add .
git commit -m "feat: your change"
git push origin main
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

# Restart Flask dev server (local)
pkill -f "flask run.*5001" && flask run --port 5001

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

### Flask Dev Server Not Starting

**Symptom**: `flask run` fails or port already in use

**Debug**:
```bash
# Check for port conflicts
lsof -i:5001

# Kill existing process
pkill -f "flask run.*5001"

# Check PostgreSQL is running
docker compose -f docker-compose.dev.yml ps
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
   curl -s http://127.0.0.1:5001/health && echo "Local app running" || echo "Local app stopped"
   ```
3. **Key architectural decisions**:
   - Flask-Login for auth (replaced Cloudflare Access Jan 2026)
   - PostgreSQL database (local via Docker, production via Docker Compose)
   - Production on Hetzner server via Cloudflare Tunnel
   - Multi-user with admin approval workflow

### Common Tasks for AI Assistants

| Task | Key Files |
|------|-----------|
| Add new feature | `routes/*.py`, `templates/*/`, `models.py` |
| Fix auth issue | `routes/auth.py`, `models.py` (User class) |
| Update UI | `templates/base.html`, `templates/*/` |
| Database changes | `models.py`, `flask db migrate`, `flask db upgrade` |
| Deployment issues | Check GitHub Actions, SSH to Hetzner |

### Don't Forget

- All routes need `@login_required` (except `/auth/*`, `/health`)
- User-scoped data must filter by `current_user.id`
- Test on `http://127.0.0.1:5001` before pushing to main
- Push to `main` triggers auto-deploy to production
- CSRF tokens required on all POST forms

---

*Last updated: January 2026*
