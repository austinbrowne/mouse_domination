# Hetzner Deployment Guide

Deploy Mouse Domination + Discord Bot to a Hetzner CX22 VPS with Docker.

## Architecture

```
Hetzner CX22 (€4.51/mo)
├── nginx (reverse proxy + SSL)
├── postgres:16 (database)
├── mouse-domination (Flask app)
└── discord-bot (livestream notifier)
```

## Quick Start

### 1. Create Hetzner Server

1. Sign up at [Hetzner Cloud](https://console.hetzner.cloud)
2. Create new project
3. Add server:
   - **Location**: Nearest to you (eu-central, us-east, etc.)
   - **Image**: Ubuntu 24.04
   - **Type**: CX22 (2 vCPU, 4GB RAM, €4.51/mo)
   - **SSH Key**: Add your public key
4. Note the IP address

### 2. Point Domain to Server

Add DNS A records:
```
yourdomain.com     → YOUR_SERVER_IP
www.yourdomain.com → YOUR_SERVER_IP
```

### 3. Run Server Setup

```bash
ssh root@YOUR_SERVER_IP

# Create your user (replace 'austin' with your username)
adduser austin
usermod -aG sudo austin

# Switch to your user
su - austin

# Download and run setup script
curl -fsSL https://raw.githubusercontent.com/austinbrowne/mouse_domination/main/deploy/scripts/setup-server.sh | bash -s yourdomain.com
```

### 4. Add Deploy Keys to GitHub

The setup script generates an SSH key. Add it to both repos:

1. Go to repo → Settings → Deploy Keys
2. Add the key (read-only is fine)
3. Repeat for both repos

### 5. Clone Repos and Configure

```bash
# Log out and back in (for docker group)
exit
ssh austin@YOUR_SERVER_IP

# Clone repos
cd /opt/apps
git clone git@github.com:austinbrowne/mouse_domination.git
git clone git@github.com:austinbrowne/discord_livestream_bot.git

# Configure
cd mouse_domination/deploy
cp .env.example .env
nano .env  # Fill in your secrets
```

### 6. Deploy

```bash
./scripts/deploy.sh yourdomain.com
```

### 7. Configure GitHub Actions

Add these secrets to **both** GitHub repos (Settings → Secrets → Actions):

| Secret | Value |
|--------|-------|
| `SERVER_IP` | Your Hetzner IP |
| `SERVER_USER` | Your username (e.g., `austin`) |
| `SSH_PRIVATE_KEY` | Contents of `~/.ssh/deploy_key` from server |

Now pushes to `main` auto-deploy!

---

## Commands Reference

```bash
cd /opt/apps/mouse_domination/deploy

# Status
docker compose ps

# Logs
docker compose logs -f                    # All
docker compose logs -f mouse-domination   # Just Flask app
docker compose logs -f discord-bot        # Just Discord bot

# Restart
docker compose restart mouse-domination
docker compose restart discord-bot

# Stop everything
docker compose down

# Full rebuild
docker compose build --no-cache
docker compose up -d

# Database shell
docker compose exec postgres psql -U mousedom -d mouse_domination

# App shell
docker compose exec mouse-domination bash
```

## SSL Certificate Renewal

Certbot auto-renews. To manually renew:

```bash
docker compose run --rm certbot renew
docker compose restart nginx
```

## Backups

Database backup:
```bash
docker compose exec postgres pg_dump -U mousedom mouse_domination > backup.sql
```

Restore:
```bash
cat backup.sql | docker compose exec -T postgres psql -U mousedom -d mouse_domination
```

## Troubleshooting

### Container won't start
```bash
docker compose logs --tail=50 container-name
```

### Can't connect to site
```bash
# Check nginx
docker compose logs nginx

# Check app health
docker compose exec mouse-domination curl http://localhost:5000/health
```

### Database connection issues
```bash
# Check postgres is running
docker compose ps postgres

# Test connection
docker compose exec postgres pg_isready
```

## Cost Breakdown

| Resource | Monthly Cost |
|----------|--------------|
| Hetzner CX22 | €4.51 (~$5) |
| Domain (optional) | ~$12/year |
| **Total** | **~$5/month** |
