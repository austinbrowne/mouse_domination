#!/bin/bash
# Mouse Domination CRM - Server Setup Script
# Run this on a fresh Ubuntu/Debian server
# Usage: curl -sSL https://raw.githubusercontent.com/.../setup-server.sh | bash

set -e

echo "=== Mouse Domination Server Setup ==="

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Update system
log_info "Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# Install Docker
log_info "Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    log_info "Docker installed. You may need to log out and back in."
else
    log_info "Docker already installed"
fi

# Install Docker Compose plugin
log_info "Installing Docker Compose..."
sudo apt-get install -y docker-compose-plugin

# Install useful tools
log_info "Installing utilities..."
sudo apt-get install -y \
    git \
    curl \
    htop \
    ncdu \
    fail2ban \
    ufw

# Configure firewall
log_info "Configuring firewall..."
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https
sudo ufw --force enable

# Configure fail2ban
log_info "Configuring fail2ban..."
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# Create app directory
log_info "Creating application directory..."
sudo mkdir -p /opt/mouse_domination
sudo chown $USER:$USER /opt/mouse_domination

# Create backup directory
mkdir -p /opt/mouse_domination/backups

# Setup swap (for low memory VPS)
log_info "Setting up swap..."
if [ ! -f /swapfile ]; then
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi

# Create systemd service for auto-start
log_info "Creating systemd service..."
sudo tee /etc/systemd/system/mouse-domination.service > /dev/null <<EOF
[Unit]
Description=Mouse Domination CRM
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/mouse_domination
ExecStart=/usr/bin/docker compose -f deploy/docker-compose.prod.yml up -d
ExecStop=/usr/bin/docker compose -f deploy/docker-compose.prod.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable mouse-domination

echo ""
log_info "=== Server Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Clone your repository to /opt/mouse_domination"
echo "2. Copy .env.example to .env and configure it"
echo "3. Update the DOMAIN in .env for your domain"
echo "4. Run: cd /opt/mouse_domination && ./scripts/deploy.sh"
echo ""
echo "Useful commands:"
echo "  docker compose -f deploy/docker-compose.prod.yml logs -f    # View logs"
echo "  docker compose -f deploy/docker-compose.prod.yml ps         # Check status"
echo "  ./scripts/deploy.sh --backup                         # Backup database"
echo ""
