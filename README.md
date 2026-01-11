# Mouse Domination CRM

A creator-focused CRM for managing brand relationships, inventory tracking, content pipeline, and revenue analytics. Built for YouTubers and content creators who work with sponsors, review units, and affiliate programs.

## Features

- **Contact & Company Management** - Track brand contacts, relationship status, and communication history
- **Inventory Tracking** - Manage review units, personal purchases, listing status, and P/L calculations
- **Content Pipeline** - Track videos, podcasts, and sponsorship deals through production stages
- **Collaboration Management** - Manage brand collaborations from pitch to completion
- **Outreach Templates** - Reusable email templates with variable substitution
- **Revenue Analytics** - Dashboard with affiliate revenue tracking and monthly trends
- **YouTube Integration** - Optional API integration for channel statistics

## Tech Stack

- **Backend**: Python 3.11, Flask 3.x, SQLAlchemy 2.x
- **Database**: SQLite (dev), PostgreSQL (prod)
- **Frontend**: Jinja2, TailwindCSS
- **Server**: Gunicorn, Caddy (reverse proxy)
- **Monitoring**: Prometheus, Grafana, Loki

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
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Initialize database
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"

# Run development server
flask run
```

The app will be available at `http://localhost:5000`.

### Docker Development

```bash
# Start with hot reload
docker compose -f docker-compose.dev.yml up

# Access at http://localhost:5000
```

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Key environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key (generate for production) | - |
| `DATABASE_URL` | Database connection string | SQLite |
| `FLASK_ENV` | Environment (development/production) | production |
| `YOUTUBE_API_KEY` | YouTube Data API key (optional) | - |
| `YOUTUBE_CHANNEL_ID` | Your YouTube channel ID (optional) | - |

Generate a secure secret key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## Production Deployment

### Using Docker Compose (Recommended)

```bash
# Configure environment
cp .env.example .env
# Edit .env with production values

# Deploy with Caddy (automatic HTTPS)
docker compose -f docker-compose.prod.yml up -d

# Check status
docker compose -f docker-compose.prod.yml ps
```

### Server Setup (Ubuntu/Debian)

```bash
# Run setup script (installs Docker, configures firewall, etc.)
./scripts/setup-server.sh

# Deploy application
./scripts/deploy.sh
```

### Manual Deployment

```bash
# Install production dependencies
pip install -r requirements-prod.txt

# Run with Gunicorn
gunicorn -c gunicorn.conf.py "app:create_app()"
```

## Project Structure

```
mouse_domination/
├── app.py                 # Application factory
├── config.py              # Configuration classes
├── models.py              # SQLAlchemy models
├── routes/                # Blueprint route handlers
│   ├── main.py           # Dashboard and health check
│   ├── contacts.py       # Contact management
│   ├── inventory.py      # Inventory tracking
│   ├── videos.py         # Video content
│   ├── podcast.py        # Podcast episodes
│   ├── collabs.py        # Collaborations
│   ├── pipeline.py       # Content pipeline
│   └── templates.py      # Outreach templates
├── templates/             # Jinja2 templates
├── static/               # Static assets
├── services/             # Business logic layer
├── utils/                # Utility functions
├── tests/                # Test suite
├── scripts/              # Deployment scripts
├── monitoring/           # Prometheus/Grafana configs
└── docs/                 # Documentation
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_routes.py -v
```

## Database Operations

### Backup (Production)

```bash
./scripts/backup.sh

# List backups
./scripts/backup.sh --list

# Restore from backup
./scripts/backup.sh --restore backups/backup_20240101_120000.sql.gz
```

### Migrations

The app uses SQLAlchemy's `db.create_all()` for schema creation. For production migrations, consider using Flask-Migrate:

```bash
flask db init
flask db migrate -m "Description"
flask db upgrade
```

## Monitoring

Enable the monitoring stack for production observability:

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.monitoring.yml up -d
```

This provides:
- **Prometheus** - Metrics collection (port 9090)
- **Grafana** - Dashboards and visualization (port 3000)
- **Loki** - Log aggregation

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Dashboard |
| `GET /health` | Health check (for load balancers) |
| `GET /contacts` | Contact list |
| `GET /inventory` | Inventory list |
| `GET /videos` | Video list |
| `GET /podcast` | Podcast episodes |
| `GET /collabs` | Collaborations |
| `GET /pipeline` | Content pipeline |
| `GET /templates` | Outreach templates |
| `GET /affiliates` | Affiliate revenue |

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is private and proprietary.

## Support

For issues and feature requests, please use the GitHub issue tracker.
