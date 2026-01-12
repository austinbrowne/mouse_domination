#!/bin/bash
# Quick deploy script - restarts app without changing tunnel URL

cd /Users/austin/Git_Repos/mouse_domination

echo "Pulling latest changes (if using git)..."
# git pull  # Uncomment if deploying from git

echo "Restarting gunicorn..."
pkill -f gunicorn
sleep 1

source .venv/bin/activate
gunicorn "app:create_app()" --bind 127.0.0.1:8000 --workers 2 --daemon

echo "Done! App restarted. Tunnel URL unchanged."
curl -s -o /dev/null -w "Health check: HTTP %{http_code}\n" http://127.0.0.1:8000/health
