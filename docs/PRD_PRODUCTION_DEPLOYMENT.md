# Production Readiness & Deployment Plan
## Mouse Domination CRM

**Version:** 1.0
**Date:** January 2026
**Status:** Draft - Pending Review

---

## Executive Summary

This document outlines the plan to take Mouse Domination CRM from development to production. The application is a Flask-based CRM for tracking contacts, companies, inventory, videos, podcast episodes, collaborations, and outreach templates.

### Current State
- **Codebase:** Complete, 166 tests passing
- **Database:** SQLite (development only)
- **Server:** Flask development server
- **Security:** Hardened, but missing production config
- **Deployment:** None

### Target State
- **Database:** PostgreSQL with automated backups
- **Server:** Gunicorn behind Nginx/Caddy
- **Security:** HTTPS, environment-based secrets, rate limiting
- **Deployment:** Docker on Oracle Cloud Free Tier (or alternative)
- **Operations:** Health checks, logging, backup automation

---

## Phase 1: Production Configuration

**Goal:** Application runs safely with production settings
**Effort:** 2-3 hours
**Priority:** Critical

### 1.1 Environment-Based Configuration

| Task | Description |
|------|-------------|
| Create `.env.example` | Template for required environment variables |
| Install python-dotenv | Load environment variables from `.env` file |
| Update `config.py` | Read secrets from environment, not hardcoded |

**Required Environment Variables:**
```bash
# .env.example
FLASK_ENV=production
SECRET_KEY=<generate-64-char-hex>
DATABASE_URL=postgresql://user:pass@localhost:5432/mouse_domination

# Optional
YOUTUBE_API_KEY=
YOUTUBE_CHANNEL_ID=
```

### 1.2 PostgreSQL Support

| Task | Description |
|------|-------------|
| Add `psycopg2-binary` to requirements | PostgreSQL driver |
| Update connection pooling config | Already configured, verify settings |
| Create database migration script | Initialize schema on fresh PostgreSQL |

**Database URL Format:**
```
postgresql://username:password@host:port/database
```

### 1.3 Production Requirements File

Create `requirements-prod.txt`:
```
-r requirements.txt
gunicorn==21.2.0
psycopg2-binary==2.9.9
python-dotenv==1.0.0
```

### 1.4 Gunicorn WSGI Server

| Task | Description |
|------|-------------|
| Create `gunicorn.conf.py` | Worker config, timeouts, logging |
| Create startup script | `./start.sh` for production launch |
| Test locally with Gunicorn | Verify app works outside Flask dev server |

**gunicorn.conf.py:**
```python
bind = "0.0.0.0:5000"
workers = 2
worker_class = "sync"
timeout = 120
keepalive = 5
errorlog = "-"
accesslog = "-"
loglevel = "info"
```

### Phase 1 Deliverables
- [ ] `.env.example` file
- [ ] Updated `config.py` with environment variable support
- [ ] `requirements-prod.txt`
- [ ] `gunicorn.conf.py`
- [ ] `start.sh` startup script
- [ ] PostgreSQL tested locally

---

## Phase 2: Containerization

**Goal:** Application packaged as Docker containers
**Effort:** 2-3 hours
**Priority:** High

### 2.1 Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

# Copy application
COPY . .

# Create non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:create_app()"]
```

### 2.2 Docker Compose

```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "5000:5000"
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/mouse_domination
      - SECRET_KEY=${SECRET_KEY}
      - FLASK_ENV=production
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=mouse_domination
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  backup:
    image: postgres:15-alpine
    environment:
      - PGPASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - ./backups:/backups
    command: >
      sh -c "while true; do
        pg_dump -h db -U postgres mouse_domination > /backups/backup_$$(date +%Y%m%d_%H%M%S).sql
        find /backups -type f -mtime +7 -delete
        sleep 86400
      done"
    depends_on:
      - db
    restart: unless-stopped

volumes:
  pgdata:
```

### 2.3 Docker Ignore

```
.git
.gitignore
.env
*.pyc
__pycache__
*.db
*.sqlite
logs/
backups/
.pytest_cache/
htmlcov/
*.md
docs/
tests/
```

### Phase 2 Deliverables
- [ ] `Dockerfile`
- [ ] `docker-compose.yml`
- [ ] `docker-compose.prod.yml` (production overrides)
- [ ] `.dockerignore`
- [ ] Local Docker testing complete

---

## Phase 3: Reverse Proxy & SSL

**Goal:** HTTPS access with proper headers
**Effort:** 1-2 hours
**Priority:** High

### 3.1 Caddy (Recommended - Automatic SSL)

**Caddyfile:**
```
mousedomination.yourdomain.com {
    reverse_proxy app:5000

    header {
        X-Frame-Options "SAMEORIGIN"
        X-Content-Type-Options "nosniff"
        X-XSS-Protection "1; mode=block"
        Referrer-Policy "strict-origin-when-cross-origin"
    }

    log {
        output file /var/log/caddy/access.log
    }
}
```

### 3.2 Docker Compose with Caddy

Add to `docker-compose.prod.yml`:
```yaml
services:
  caddy:
    image: caddy:2-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
      - caddy_config:/config
    depends_on:
      - app
    restart: unless-stopped

volumes:
  caddy_data:
  caddy_config:
```

### Phase 3 Deliverables
- [ ] `Caddyfile`
- [ ] Updated `docker-compose.prod.yml`
- [ ] SSL certificate auto-provisioning tested

---

## Phase 4: Cloud Deployment

**Goal:** Application running on cloud infrastructure
**Effort:** 2-3 hours
**Priority:** High

### 4.1 Oracle Cloud Free Tier (Recommended)

**Why Oracle Cloud:**
- 2 ARM VMs free forever (4 OCPU, 24GB RAM total)
- 200GB block storage free
- Enough for this app + Discord bot + future projects

**Setup Steps:**

1. **Create Oracle Cloud Account**
   - Sign up at cloud.oracle.com
   - Verify identity (credit card required, won't be charged)

2. **Create Compute Instance**
   ```
   Shape: VM.Standard.A1.Flex (ARM)
   OCPU: 2
   Memory: 12GB
   OS: Ubuntu 22.04
   ```

3. **Configure Security List**
   ```
   Ingress Rules:
   - Port 22 (SSH)
   - Port 80 (HTTP)
   - Port 443 (HTTPS)
   ```

4. **Install Docker**
   ```bash
   sudo apt update
   sudo apt install docker.io docker-compose-v2
   sudo usermod -aG docker $USER
   ```

5. **Deploy Application**
   ```bash
   git clone <your-repo>
   cd mouse_domination
   cp .env.example .env
   # Edit .env with production values
   docker compose -f docker-compose.prod.yml up -d
   ```

### 4.2 Alternative: Railway

**For simpler deployment (no server management):**

1. Connect GitHub repo to Railway
2. Add PostgreSQL plugin
3. Set environment variables
4. Deploy

**railway.json:**
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE"
  },
  "deploy": {
    "startCommand": "gunicorn -c gunicorn.conf.py 'app:create_app()'"
  }
}
```

### Phase 4 Deliverables
- [ ] Cloud account created
- [ ] VM/instance provisioned
- [ ] Docker installed
- [ ] Application deployed
- [ ] Domain configured (optional)

---

## Phase 5: Operations & Monitoring

**Goal:** Application stays healthy, issues detected early
**Effort:** 1-2 hours
**Priority:** Medium

### 5.1 Health Check Endpoint

Add to `routes/main.py`:
```python
@main_bp.route('/health')
def health_check():
    try:
        db.session.execute(text('SELECT 1'))
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500
```

### 5.2 Backup Verification

**Weekly backup test script:**
```bash
#!/bin/bash
# verify-backup.sh

LATEST_BACKUP=$(ls -t /backups/*.sql | head -1)
pg_restore --dry-run "$LATEST_BACKUP" 2>/dev/null

if [ $? -eq 0 ]; then
    echo "Backup verification passed: $LATEST_BACKUP"
else
    echo "BACKUP VERIFICATION FAILED" | mail -s "Backup Alert" your@email.com
fi
```

### 5.3 Simple Uptime Monitoring

**Free options:**
- UptimeRobot (free tier: 50 monitors)
- Healthchecks.io (free tier: 20 checks)
- Cronitor (free tier: 5 monitors)

**Configure:**
- Monitor `/health` endpoint
- Alert on 5xx errors or timeout
- Check interval: 5 minutes

### 5.4 Log Aggregation (Optional)

For future scale, consider:
- Papertrail (free tier available)
- Logtail (free tier available)
- Self-hosted Loki + Grafana

### Phase 5 Deliverables
- [ ] `/health` endpoint added
- [ ] Backup verification script
- [ ] Uptime monitoring configured
- [ ] Alert notifications working

---

## Security Checklist

### Pre-Deployment
- [ ] `SECRET_KEY` is unique, 64+ characters
- [ ] `DEBUG=False` in production
- [ ] Database password is strong (20+ chars)
- [ ] `.env` file is not in git
- [ ] No hardcoded secrets in codebase

### Post-Deployment
- [ ] HTTPS working (check SSL Labs)
- [ ] Security headers present (check securityheaders.com)
- [ ] Database not exposed to internet
- [ ] SSH key-only authentication (no password)
- [ ] Firewall rules minimal (only 22, 80, 443)

---

## Rollback Plan

### Application Rollback
```bash
# List previous images
docker images mouse_domination

# Rollback to previous version
docker compose down
docker tag mouse_domination:previous mouse_domination:latest
docker compose up -d
```

### Database Rollback
```bash
# Stop application
docker compose stop app

# Restore from backup
docker exec -i db psql -U postgres mouse_domination < /backups/backup_YYYYMMDD.sql

# Restart application
docker compose start app
```

---

## Cost Summary

| Option | Monthly Cost | Notes |
|--------|--------------|-------|
| Oracle Cloud | $0 | Free tier forever |
| Railway | $0-5 | Free tier may suffice |
| DigitalOcean | $6 | Cheapest droplet |
| Self-hosted | $0 | Electricity only |

---

## Timeline

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 1: Production Config | Day 1 | None |
| Phase 2: Containerization | Day 1-2 | Phase 1 |
| Phase 3: Reverse Proxy | Day 2 | Phase 2 |
| Phase 4: Deployment | Day 2-3 | Phase 3 |
| Phase 5: Operations | Day 3 | Phase 4 |

**Total estimated time:** 2-3 days (part-time)

---

## Approval

- [ ] Technical approach approved
- [ ] Cloud provider selected: ________________
- [ ] Domain decision: ________________
- [ ] Ready to proceed

---

## Next Steps

Upon approval:
1. Begin Phase 1 implementation
2. Set up cloud account (if Oracle/other chosen)
3. Register domain (if desired)

---

*Document prepared for review. Please provide feedback or approval to proceed.*
