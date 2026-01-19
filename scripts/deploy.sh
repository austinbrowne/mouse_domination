#!/bin/bash
# Mouse Domination CRM - Deployment Script
# Usage: ./scripts/deploy.sh [environment]
# Environments: staging, production

set -e

ENVIRONMENT=${1:-production}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Mouse Domination Deployment ==="
echo "Environment: $ENVIRONMENT"
echo "Project Dir: $PROJECT_DIR"
echo ""

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi

    if ! command -v docker compose &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi

    if [ ! -f "$PROJECT_DIR/.env" ]; then
        log_error ".env file not found. Copy .env.example and configure it."
        exit 1
    fi

    log_info "Prerequisites check passed"
}

# Validate environment variables
validate_env() {
    log_info "Validating environment variables..."

    source "$PROJECT_DIR/.env"

    if [ -z "$SECRET_KEY" ] || [ "$SECRET_KEY" = "generate-with-python-c-import-secrets-print-secrets-token_hex-32" ]; then
        log_error "SECRET_KEY is not set or is using default value"
        log_info "Generate one with: python -c 'import secrets; print(secrets.token_hex(32))'"
        exit 1
    fi

    if [ -z "$POSTGRES_PASSWORD" ] || [ "$POSTGRES_PASSWORD" = "mouse" ]; then
        log_warn "POSTGRES_PASSWORD is using default value. Consider changing for production."
    fi

    log_info "Environment validation passed"
}

# Pull latest code (if in git repo)
pull_latest() {
    if [ -d "$PROJECT_DIR/.git" ]; then
        log_info "Pulling latest changes..."
        cd "$PROJECT_DIR"
        git pull origin main || log_warn "Could not pull latest changes"
    fi
}

# Build and deploy
deploy() {
    cd "$PROJECT_DIR"

    log_info "Building Docker images..."
    docker compose -f deploy/docker-compose.prod.yml build --no-cache

    log_info "Stopping existing containers..."
    docker compose -f deploy/docker-compose.prod.yml down

    log_info "Starting containers..."
    docker compose -f deploy/docker-compose.prod.yml up -d

    log_info "Waiting for services to be healthy..."
    sleep 10

    # Check health
    if curl -sf http://localhost:5000/health > /dev/null 2>&1; then
        log_info "Application is healthy!"
    else
        log_warn "Health check failed. Checking logs..."
        docker compose -f deploy/docker-compose.prod.yml logs --tail=50 app
    fi
}

# Show status
show_status() {
    log_info "Container status:"
    docker compose -f deploy/docker-compose.prod.yml ps
    echo ""
    log_info "Recent logs:"
    docker compose -f deploy/docker-compose.prod.yml logs --tail=20
}

# Backup database
backup_db() {
    log_info "Creating database backup..."
    BACKUP_FILE="backup_$(date +%Y%m%d_%H%M%S).sql"
    docker compose -f deploy/docker-compose.prod.yml exec -T db pg_dump -U mouse mouse_domination > "$PROJECT_DIR/backups/$BACKUP_FILE"
    log_info "Backup saved to: backups/$BACKUP_FILE"
}

# Main
main() {
    check_prerequisites
    validate_env

    case "$2" in
        --pull)
            pull_latest
            ;;
        --backup)
            backup_db
            exit 0
            ;;
        --status)
            show_status
            exit 0
            ;;
    esac

    deploy
    show_status

    echo ""
    log_info "Deployment complete!"
    log_info "Access the app at: https://your-domain.com"
}

main "$@"
