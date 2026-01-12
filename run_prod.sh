#!/bin/bash
# Production runner for Mouse Domination

cd /Users/austin/Git_Repos/mouse_domination
source .venv/bin/activate

# Set production environment
export FLASK_ENV=production
export SECRET_KEY=$(cat .secret_key 2>/dev/null || python -c "import secrets; print(secrets.token_hex(32))")

# Save secret key for persistence
echo "$SECRET_KEY" > .secret_key

# Create logs directory if needed
mkdir -p logs

# Run with gunicorn (production WSGI server)
# Note: Using port 8000 since AirPlay uses 5000 on macOS
exec gunicorn "app:create_app()" \
    --bind 127.0.0.1:8000 \
    --workers 2 \
    --access-logfile logs/access.log \
    --error-logfile logs/error.log \
    --capture-output
