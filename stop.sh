#!/bin/bash
# Stop Mouse Domination and Cloudflare Tunnel

echo "Stopping Mouse Domination..."

# Stop cloudflared
if pgrep -f "cloudflared tunnel" > /dev/null; then
    echo "Stopping Cloudflare Tunnel..."
    pkill -f "cloudflared tunnel"
    echo "Tunnel stopped."
else
    echo "Cloudflare Tunnel not running."
fi

# Stop gunicorn
if pgrep -f "gunicorn.*app:create_app" > /dev/null; then
    echo "Stopping gunicorn..."
    pkill -f gunicorn
    echo "Gunicorn stopped."
else
    echo "Gunicorn not running."
fi

# Clean up
rm -f /tmp/cloudflared_output.log

echo "Done. All services stopped."
