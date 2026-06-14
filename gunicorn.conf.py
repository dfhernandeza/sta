# =============================================================
# Gunicorn configuration file for STA production server
# Usage: gunicorn -c gunicorn.conf.py sta_project.wsgi
# =============================================================

import multiprocessing

# Worker count: (2 × CPU cores) + 1
workers = multiprocessing.cpu_count() * 2 + 1

# Worker class
worker_class = "sync"

# Timeout (seconds)
timeout = 120

# Binding
bind = "127.0.0.1:8000"

# Process name
proc_name = "sta_gunicorn"

# Logging
accesslog = "/var/log/sta/gunicorn_access.log"
errorlog  = "/var/log/sta/gunicorn_error.log"
loglevel  = "info"

# Restart workers after this many requests (prevents memory leaks)
max_requests = 1000
max_requests_jitter = 50

# Graceful timeout
graceful_timeout = 30

# Keep-alive
keepalive = 2

# Preload app
preload_app = True
