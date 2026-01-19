#!/bin/bash
# Mouse Domination CRM - Database Backup Script
# Usage: ./scripts/backup.sh [--restore backup_file.sql]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/backups"
COMPOSE_FILE="$PROJECT_DIR/deploy/docker-compose.prod.yml"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Load environment
if [ -f "$PROJECT_DIR/.env" ]; then
    source "$PROJECT_DIR/.env"
fi

POSTGRES_USER=${POSTGRES_USER:-mousedom}
POSTGRES_DB=${POSTGRES_DB:-mousedom}

backup() {
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="$BACKUP_DIR/backup_${TIMESTAMP}.sql"

    log_info "Creating backup..."

    docker compose -f "$COMPOSE_FILE" exec -T db \
        pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > "$BACKUP_FILE"

    # Compress backup
    gzip "$BACKUP_FILE"
    BACKUP_FILE="${BACKUP_FILE}.gz"

    log_info "Backup created: $BACKUP_FILE"
    log_info "Size: $(du -h "$BACKUP_FILE" | cut -f1)"

    # Cleanup old backups (keep last 7)
    log_info "Cleaning up old backups..."
    ls -t "$BACKUP_DIR"/backup_*.sql.gz 2>/dev/null | tail -n +8 | xargs -r rm

    # List remaining backups
    log_info "Available backups:"
    ls -lh "$BACKUP_DIR"/backup_*.sql.gz 2>/dev/null || echo "No backups found"
}

restore() {
    BACKUP_FILE="$1"

    if [ ! -f "$BACKUP_FILE" ]; then
        log_error "Backup file not found: $BACKUP_FILE"
        exit 1
    fi

    log_info "Restoring from: $BACKUP_FILE"

    read -p "This will overwrite the current database. Continue? (y/N) " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        log_info "Restore cancelled"
        exit 0
    fi

    # Decompress if needed
    if [[ "$BACKUP_FILE" == *.gz ]]; then
        log_info "Decompressing backup..."
        gunzip -k "$BACKUP_FILE"
        BACKUP_FILE="${BACKUP_FILE%.gz}"
        CLEANUP_FILE="$BACKUP_FILE"
    fi

    log_info "Restoring database..."
    cat "$BACKUP_FILE" | docker compose -f "$COMPOSE_FILE" exec -T db \
        psql -U "$POSTGRES_USER" "$POSTGRES_DB"

    # Cleanup decompressed file
    if [ -n "$CLEANUP_FILE" ]; then
        rm "$CLEANUP_FILE"
    fi

    log_info "Database restored successfully!"
}

list() {
    log_info "Available backups:"
    ls -lh "$BACKUP_DIR"/backup_*.sql.gz 2>/dev/null || echo "No backups found"
}

# Main
case "$1" in
    --restore)
        if [ -z "$2" ]; then
            log_error "Please specify backup file: ./backup.sh --restore backup_file.sql.gz"
            exit 1
        fi
        restore "$2"
        ;;
    --list)
        list
        ;;
    *)
        backup
        ;;
esac
