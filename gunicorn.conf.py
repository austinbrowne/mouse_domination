"""Gunicorn configuration for production deployment."""
import os

# Server socket
bind = os.environ.get('GUNICORN_BIND', '0.0.0.0:5000')

# Worker processes
workers = int(os.environ.get('GUNICORN_WORKERS', 2))
worker_class = 'sync'
worker_connections = 1000
timeout = 120
keepalive = 5

# Restart workers after this many requests (prevents memory leaks)
max_requests = 1000
max_requests_jitter = 50

# Logging
errorlog = '-'  # stderr
accesslog = '-'  # stdout
loglevel = os.environ.get('GUNICORN_LOG_LEVEL', 'info')
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = 'mouse_domination'

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (uncomment if terminating SSL at Gunicorn)
# keyfile = '/path/to/key.pem'
# certfile = '/path/to/cert.pem'
