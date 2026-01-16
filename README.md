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
- **Database**: PostgreSQL (recommended), SQLite (fallback)
- **Frontend**: Jinja2, TailwindCSS (CDN), Alpine.js
- **Server**: Gunicorn (production), Flask dev server (local)

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

### Local PostgreSQL (Recommended)

For dev/prod parity, use local PostgreSQL instead of SQLite:

```bash
# Start local PostgreSQL
docker compose -f docker-compose.dev.yml up -d

# Add to .env (or uncomment in .env.example)
echo "DATABASE_URL=postgresql://mouse:mouse@localhost:5433/mouse_domination" >> .env

# Run migrations to create tables
flask db upgrade

# (Optional) Sync data from production
python scripts/sync_from_production.py
```

This matches production's PostgreSQL setup and avoids SQLite ↔ PostgreSQL type conversion issues.

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
| `DISCORD_BOT_TOKEN` | Discord bot token for community topic sourcing | No |

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

## Discord Integration (Community Topic Sourcing)

The Episode Guide feature supports importing topics from Discord. Community members can react to messages with specific emoji, and those messages can be imported as episode guide items.

### Discord Bot Setup

1. **Create a Discord Application**
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Click "New Application" and give it a name
   - Go to the "Bot" section and click "Add Bot"

2. **Configure Bot Settings**
   - Under "Privileged Gateway Intents", enable:
     - **Message Content Intent** (required to read message content)
   - Copy the bot token and add it to your `.env` file:
     ```bash
     DISCORD_BOT_TOKEN=your_bot_token_here
     ```

3. **Invite Bot to Your Server**
   - Go to "OAuth2" > "URL Generator"
   - Select scopes: `bot`
   - Select bot permissions:
     - Read Messages/View Channels
     - Read Message History
   - Copy the generated URL and open it to invite the bot to your server

4. **Get Server and Channel IDs**
   - Enable Developer Mode in Discord (User Settings > Advanced > Developer Mode)
   - Right-click your server name → "Copy Server ID"
   - Right-click the channel you want to monitor → "Copy Channel ID"

### In-App Configuration

1. Go to **Episode Guide** > **Templates**
2. Edit a template (or create one)
3. Scroll to **Discord Community Topic Sourcing**
4. Enter:
   - **Server ID**: Your Discord server ID
   - **Channel ID**: The channel to monitor for reactions
   - **Bot Token Env Var**: Environment variable name (default: `DISCORD_BOT_TOKEN`)
5. Click **Save Discord Settings**
6. Click **Test Connection** to verify it works

### Emoji Mapping

After saving Discord settings, configure which emoji reactions map to which sections:

1. In the template form, under "Emoji Mappings"
2. Click **+ Add Mapping**
3. Enter the emoji (Unicode like 🎮 or custom like `<:mice:123456789>`)
4. Select the target section (e.g., "News - Mice", "Community Recap")
5. Repeat for each emoji you want to track

### Importing Topics

1. Open an Episode Guide for editing
2. Click the **Discord Import** button (only appears if Discord is configured)
3. Review the fetched messages - each shows:
   - Original Discord message (expandable)
   - Editable title and links
   - Section dropdown to categorize the topic
4. Select/deselect messages to import
5. Click **Import Selected**

Messages are tracked to prevent duplicate imports.

### Custom Emoji Format

For custom server emoji, use the format: `<:emoji_name:emoji_id>`

To get a custom emoji's ID:
1. Type the emoji in Discord with a backslash: `\:your_emoji:`
2. It will show: `<:emoji_name:123456789012345678>`
3. Use that full string in the emoji mapping

## Production Deployment

Production uses Docker Compose with PostgreSQL and Cloudflare Tunnel for HTTPS.

### Required .env File

Create `.env` on the server:

```bash
SECRET_KEY=<generate-with-python>
DATABASE_URL=postgresql://<user>:<pass>@db:5432/<dbname>
POSTGRES_USER=<user>
POSTGRES_PASSWORD=<pass>
POSTGRES_DB=<dbname>
```

Generate secret key: `python3 -c "import secrets; print(secrets.token_hex(32))"`

### Docker Commands

```bash
# Start services
docker compose up -d --build

# View logs
docker compose logs -f app

# Run database migrations
docker compose exec app flask db upgrade

# Database shell
docker compose exec db psql -U <user> -d <dbname>

# Full reset (WARNING: deletes all data)
docker compose down -v
docker compose up -d
```

**Note:** The database service is named `db` in docker-compose.yml.

### Cloudflare Tunnel

HTTPS is provided by Cloudflare Tunnel (dashboard-managed).

1. Create tunnel in Cloudflare Zero Trust dashboard
2. Add public hostname pointing to `http://localhost:5000`
3. Run the connector install command on the server

**Important:** Use Cloudflare Tunnel's CNAME, not an A record pointing to the server IP.

### Data Migration

Export from local SQLite and import to production PostgreSQL:

```bash
# Local: export data
python scripts/export_for_postgres.py

# Copy to server
scp scripts/data_export.sql user@server:/tmp/

# Server: import data
docker compose exec app flask db upgrade
docker compose exec -T db psql -U <user> -d <dbname> < /tmp/data_export.sql
```

### Server-Specific Details

See `DEPLOYMENT.md` (gitignored) for credentials, IPs, and server-specific commands.

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
├── scripts/              # Migration and utility scripts
│   ├── backup_db.sh      # Database backup (legacy)
│   ├── migrate_flask_login.py  # Auth migration
│   └── sync_from_production.py # Sync data from production
└── backups/              # Database backups
```

## Database Operations

### Migrations (Alembic/Flask-Migrate)

Database schema changes are managed with Flask-Migrate (Alembic wrapper).

**Making schema changes:**

```bash
# 1. Modify models.py with your changes

# 2. Generate migration locally
source .venv/bin/activate
flask db migrate -m "Add avatar_url to users"

# 3. Review the generated migration in migrations/versions/

# 4. Commit and push
git add migrations/
git commit -m "feat: Add avatar_url to users"
git push origin main
```

Migrations auto-run on deploy when the `migrations/` folder changes.

**Manual migration commands (on server):**

```bash
cd /opt/apps/infra

# Run pending migrations
docker compose exec mouse-domination flask db upgrade

# Mark database as current (without running migrations)
docker compose exec mouse-domination flask db stamp head

# View migration history
docker compose exec mouse-domination flask db history

# Rollback one migration
docker compose exec mouse-domination flask db downgrade
```

**First-time setup (existing database):**

```bash
# Mark existing database as up-to-date
docker compose exec mouse-domination flask db stamp head
```

### Backup (SQLite)

```bash
./scripts/backup_db.sh
```

Backups are stored in `backups/` directory.

### Add Indexes (One-time)

```bash
docker compose exec mouse-domination python -m scripts.add_indexes
```

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
