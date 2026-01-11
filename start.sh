#!/bin/bash
set -e

# Mouse Domination CRM - Production Startup Script

echo "Starting Mouse Domination CRM..."

# Check for required environment variables
if [ -z "$SECRET_KEY" ]; then
    echo "ERROR: SECRET_KEY environment variable is not set"
    echo "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
    exit 1
fi

if [ -z "$DATABASE_URL" ]; then
    echo "WARNING: DATABASE_URL not set, using SQLite (not recommended for production)"
fi

# Run database migrations if needed
echo "Checking database..."
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all(); print('Database ready')"

# Start Gunicorn
echo "Starting Gunicorn..."
exec gunicorn -c gunicorn.conf.py "app:create_app()"
