#!/bin/bash
# Hetzner CX22 Server Setup Script
# Run this once on a fresh Ubuntu 22.04/24.04 server

set -e

echo "========================================="
echo "  Hetzner Server Setup for Docker Apps"
echo "========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}Don't run this script as root. Run as your regular user.${NC}"
    exit 1
fi

# Get domain from argument or prompt
DOMAIN=${1:-}
if [ -z "$DOMAIN" ]; then
    read -p "Enter your domain (e.g., mousedomination.com): " DOMAIN
fi

echo -e "${GREEN}Setting up server for: $DOMAIN${NC}"

# ===================
# SYSTEM UPDATES
# ===================
echo -e "\n${YELLOW}[1/6] Updating system...${NC}"
sudo apt update && sudo apt upgrade -y

# ===================
# INSTALL DOCKER
# ===================
echo -e "\n${YELLOW}[2/6] Installing Docker...${NC}"

# Remove old versions
sudo apt remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true

# Install prerequisites
sudo apt install -y ca-certificates curl gnupg lsb-release

# Add Docker GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add Docker repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add user to docker group (no sudo needed for docker commands)
sudo usermod -aG docker $USER

echo -e "${GREEN}Docker installed successfully${NC}"

# ===================
# INSTALL EXTRAS
# ===================
echo -e "\n${YELLOW}[3/6] Installing utilities...${NC}"
sudo apt install -y git htop ncdu fail2ban ufw

# ===================
# CONFIGURE FIREWALL
# ===================
echo -e "\n${YELLOW}[4/6] Configuring firewall...${NC}"
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https
sudo ufw --force enable

echo -e "${GREEN}Firewall configured (SSH, HTTP, HTTPS allowed)${NC}"

# ===================
# CREATE DIRECTORY STRUCTURE
# ===================
echo -e "\n${YELLOW}[5/6] Creating app directories...${NC}"

sudo mkdir -p /opt/apps
sudo chown $USER:$USER /opt/apps

mkdir -p /opt/apps/mouse_domination
mkdir -p /opt/apps/discord_livestream_bot
mkdir -p /opt/apps/deploy

echo -e "${GREEN}Directories created at /opt/apps/${NC}"

# ===================
# CREATE DEPLOY KEY
# ===================
echo -e "\n${YELLOW}[6/6] Setting up SSH deploy key...${NC}"

if [ ! -f ~/.ssh/deploy_key ]; then
    ssh-keygen -t ed25519 -f ~/.ssh/deploy_key -N "" -C "deploy@$DOMAIN"
    echo -e "${GREEN}Deploy key created${NC}"
else
    echo -e "${YELLOW}Deploy key already exists${NC}"
fi

# ===================
# SUMMARY
# ===================
echo ""
echo "========================================="
echo -e "${GREEN}  Setup Complete!${NC}"
echo "========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. LOG OUT AND BACK IN (for docker group to take effect):"
echo "   exit"
echo "   ssh your-user@your-server"
echo ""
echo "2. Add this deploy key to your GitHub repos:"
echo "   (Settings → Deploy Keys → Add deploy key)"
echo ""
echo -e "${YELLOW}--- PUBLIC KEY (copy this) ---${NC}"
cat ~/.ssh/deploy_key.pub
echo -e "${YELLOW}--- END KEY ---${NC}"
echo ""
echo "3. Clone your repos:"
echo "   cd /opt/apps"
echo "   git clone git@github.com:austinbrowne/mouse_domination.git"
echo "   git clone git@github.com:austinbrowne/discord_livestream_bot.git"
echo ""
echo "4. Configure and start:"
echo "   cd /opt/apps/mouse_domination/deploy"
echo "   cp .env.example .env"
echo "   nano .env  # Fill in your secrets"
echo "   ./scripts/deploy.sh $DOMAIN"
echo ""
