#!/bin/bash
# Automated SQLite backup script for Mouse Domination
# Keeps the last 7 daily backups

set -e

# Configuration
DB_PATH="/Users/austin/Git_Repos/mouse_domination/mouse_domination.db"
BACKUP_DIR="/Users/austin/Git_Repos/mouse_domination/backups"
KEEP_DAYS=7

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Check if database exists
if [ ! -f "$DB_PATH" ]; then
    echo "Error: Database not found at $DB_PATH"
    exit 1
fi

# Create backup with timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/mouse_domination_$TIMESTAMP.db"

# Use SQLite's backup command for safe copy (handles locks properly)
sqlite3 "$DB_PATH" ".backup '$BACKUP_FILE'"

echo "Backup created: $BACKUP_FILE"

# Remove backups older than KEEP_DAYS
find "$BACKUP_DIR" -name "mouse_domination_*.db" -type f -mtime +$KEEP_DAYS -delete

# Show current backups
echo "Current backups:"
ls -lh "$BACKUP_DIR"/mouse_domination_*.db 2>/dev/null | tail -5
