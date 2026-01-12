# Mouse Domination CRM

A creator-focused CRM for managing brand relationships, inventory tracking, content pipeline, and revenue analytics. Built for YouTubers and content creators who work with sponsors, review units, and affiliate programs.

## Features

- **Contact & Company Management** - Track brand contacts, relationship status, and communication history
- **Inventory Tracking** - Manage review units, personal purchases, listing status, and P/L calculations
- **Content Pipeline** - Track sponsorship deals through production stages
- **Collaboration Management** - Manage brand collaborations from pitch to completion
- **Episode Guide (MouseCast)** - Podcast episode planning with timestamps, links, and poll questions
- **Outreach Templates** - Reusable email templates with variable substitution
- **Revenue Analytics** - Dashboard with affiliate revenue tracking and monthly trends
- **Multi-User Support** - User registration with admin approval workflow

## Tech Stack

- **Backend**: Python 3.11+, Flask 3.x, SQLAlchemy 2.x
- **Authentication**: Flask-Login, Argon2id password hashing
- **Database**: SQLite (dev/single-user), PostgreSQL (optional)
- **Frontend**: Jinja2, TailwindCSS (CDN), Alpine.js
- **Server**: Gunicorn, Cloudflare Tunnel (HTTPS)

## Quick Start

### Prerequisites

- Python 3.11+
- pip

### Local Development

```bash
# Clone the repository
git clone https://github.com/austinbrowne/mouse_domination.git
cd mouse_domination

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env and set SECRET_KEY (generate with: python -c "import secrets; print(secrets.token_hex(32))")

# Initialize database and create admin user
python scripts/migrate_flask_login.py

# Run development server
flask run --port 5001
```

The app will be available at `http://localhost:5001`.

### First-Time Setup

1. Run the migration script which will prompt you to create an admin user
2. Log in with your admin credentials
3. New users can register at `/auth/register` and require admin approval

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Key environment variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `SECRET_KEY` | Flask secret key (generate for production) | Yes |
| `FLASK_ENV` | Environment (development/production) | Yes |
| `DATABASE_URL` | Database connection string | No (defaults to SQLite) |
| `YOUTUBE_API_KEY` | YouTube Data API key | No |
| `YOUTUBE_CHANNEL_ID` | Your YouTube channel ID | No |

Generate a secure secret key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## Authentication

The app uses Flask-Login with the following security features:

- **Argon2id** password hashing (OWASP recommended)
- **Rate limiting** - 5 login attempts per minute
- **Progressive lockout** - Account locks after failed attempts (5min → 15min → 1hr → 24hr)
- **Admin approval** - New user registrations require admin approval
- **Session protection** - Strong session protection with secure cookies

### User Roles

- **Admin**: Can approve/reject users, manage user roles
- **User**: Access to all CRM features for their own data

## Production Deployment

### Self-Hosted with Cloudflare Tunnel (Current Setup)

```bash
# Start gunicorn
source .venv/bin/activate
gunicorn "app:create_app()" --bind 127.0.0.1:8000 --workers 2 --daemon

# Or use deploy script
./deploy.sh
```

Cloudflare Tunnel handles HTTPS and routes traffic to localhost:8000.

### Quick Deploy (Restart App)

```bash
./deploy.sh
```

## Project Structure

```
mouse_domination/
├── app.py                 # Application factory
├── config.py              # Configuration classes
├── constants.py           # Dropdown choices, constants
├── extensions.py          # Flask extensions (db, csrf, login_manager)
├── models.py              # SQLAlchemy models (User, Inventory, etc.)
├── routes/                # Blueprint route handlers
│   ├── admin.py          # User management (admin only)
│   ├── auth.py           # Login, logout, registration
│   ├── main.py           # Dashboard and health check
│   ├── contacts.py       # Contact management
│   ├── companies.py      # Company management
│   ├── inventory.py      # Inventory tracking
│   ├── affiliates.py     # Affiliate revenue
│   ├── collabs.py        # Collaborations
│   ├── pipeline.py       # Sponsorship pipeline
│   ├── templates.py      # Outreach templates
│   └── episode_guide.py  # MouseCast episode planning
├── templates/             # Jinja2 templates
│   ├── admin/            # User management
│   ├── auth/             # Login, register, pending
│   ├── inventory/        # Inventory CRUD
│   ├── contacts/         # Contact CRUD
│   ├── companies/        # Company CRUD
│   ├── episode_guide/    # MouseCast templates
│   └── ...
├── utils/                # Utility functions
├── scripts/              # Deployment and migration scripts
│   ├── deploy.sh         # Restart gunicorn
│   ├── backup_db.sh      # SQLite backup
│   └── migrate_flask_login.py  # Auth migration
└── backups/              # Database backups
```

## Database Operations

### Backup (SQLite)

```bash
./scripts/backup_db.sh
```

Backups are stored in `backups/` directory.

### Schema Updates

The app auto-creates tables on startup. For column additions, use the migration scripts in `scripts/`.

## API Endpoints

All routes except `/auth/*` and `/health` require authentication.

| Endpoint | Description |
|----------|-------------|
| `GET /` | Dashboard |
| `GET /health` | Health check (public) |
| `GET /auth/login` | Login page |
| `GET /auth/register` | Registration page |
| `GET /admin/users` | User management (admin only) |
| `GET /inventory` | Inventory list |
| `GET /contacts` | Contact list |
| `GET /companies` | Company list |
| `GET /guide` | Episode guide list |
| `GET /collabs` | Collaborations |
| `GET /pipeline` | Sponsorship pipeline |
| `GET /templates` | Outreach templates |
| `GET /affiliates` | Affiliate revenue |

## License

This project is private and proprietary.
