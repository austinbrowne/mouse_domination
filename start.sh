#!/bin/bash
# Start Mouse Domination with Cloudflare Tunnel

cd /Users/austin/Git_Repos/mouse_domination

echo "Starting Mouse Domination..."

# Check if already running
if pgrep -f "gunicorn.*app:create_app" > /dev/null; then
    echo "Gunicorn already running. Use ./stop.sh first or ./deploy.sh to restart."
    exit 1
fi

# Start gunicorn
echo "Starting gunicorn on port 8000..."
source .venv/bin/activate
gunicorn "app:create_app()" --bind 127.0.0.1:8000 --workers 2 --daemon

sleep 2

# Verify gunicorn started
if ! curl -s -o /dev/null http://127.0.0.1:8000/health; then
    echo "ERROR: Gunicorn failed to start"
    exit 1
fi
echo "Gunicorn running."

# Start permanent cloudflared tunnel
echo "Starting Cloudflare Tunnel..."
cloudflared tunnel run mouse-domination > /tmp/cloudflared_output.log 2>&1 &

sleep 3

# Check tunnel is running
if pgrep -f "cloudflared tunnel run" > /dev/null; then
    echo ""
    echo "=========================================="
    echo "  Mouse Domination is LIVE!"
    echo "  URL: https://app.dazztrazak.com"
    echo "=========================================="
    echo ""
else
    echo "WARNING: Tunnel may not have started. Check /tmp/cloudflared_output.log"
fi

echo "To stop: ./stop.sh"
