#!/bin/bash
# Deploy script - run after initial setup or to redeploy
# Usage: ./deploy.sh yourdomain.com

set -e

DOMAIN=${1:-}
DEPLOY_DIR="/opt/apps/mouse_domination/deploy"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

cd "$DEPLOY_DIR"

# Check for .env file
if [ ! -f .env ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    echo "Copy .env.example to .env and fill in your secrets:"
    echo "  cp .env.example .env"
    echo "  nano .env"
    exit 1
fi

# Load environment
source .env

# Get domain from .env or argument
DOMAIN=${DOMAIN:-$1}
if [ -z "$DOMAIN" ]; then
    echo -e "${RED}Error: No domain specified${NC}"
    echo "Usage: ./deploy.sh yourdomain.com"
    echo "Or set DOMAIN in .env file"
    exit 1
fi

echo "========================================="
echo "  Deploying to: $DOMAIN"
echo "========================================="

# ===================
# UPDATE NGINX CONFIG
# ===================
echo -e "\n${YELLOW}[1/4] Configuring nginx for $DOMAIN...${NC}"
sed -i "s/YOUR_DOMAIN/$DOMAIN/g" nginx/sites/mouse-domination.conf

# ===================
# GET SSL CERTIFICATE
# ===================
echo -e "\n${YELLOW}[2/4] Setting up SSL certificate...${NC}"

# First, start nginx without SSL for certbot challenge
# Create a temporary nginx config for initial cert
mkdir -p nginx/sites-initial
cat > nginx/sites-initial/initial.conf << EOF
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 200 'Setting up SSL...';
        add_header Content-Type text/plain;
    }
}
EOF

# Start nginx with initial config
docker compose -f docker-compose.yml run --rm -d \
    -v $(pwd)/nginx/sites-initial:/etc/nginx/sites:ro \
    nginx || true

# Get certificate
docker compose run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email admin@$DOMAIN \
    --agree-tos \
    --no-eff-email \
    -d $DOMAIN \
    -d www.$DOMAIN || {
        echo -e "${YELLOW}Certbot failed - continuing without SSL for now${NC}"
        echo "You can run certbot manually later"
    }

# Clean up initial config
rm -rf nginx/sites-initial

# ===================
# BUILD AND START
# ===================
echo -e "\n${YELLOW}[3/4] Building and starting containers...${NC}"

docker compose build
docker compose up -d

# ===================
# VERIFY
# ===================
echo -e "\n${YELLOW}[4/4] Verifying deployment...${NC}"
sleep 10

if docker compose ps | grep -q "Up"; then
    echo -e "${GREEN}Containers are running!${NC}"
    docker compose ps
else
    echo -e "${RED}Some containers may have failed. Check logs:${NC}"
    docker compose logs --tail=50
    exit 1
fi

echo ""
echo "========================================="
echo -e "${GREEN}  Deployment Complete!${NC}"
echo "========================================="
echo ""
echo "Your apps should be available at:"
echo "  - https://$DOMAIN (Mouse Domination)"
echo "  - Discord bot is running in background"
echo ""
echo "Useful commands:"
echo "  docker compose ps          # Status"
echo "  docker compose logs -f     # Follow logs"
echo "  docker compose restart     # Restart all"
echo "  docker compose down        # Stop all"
echo ""
