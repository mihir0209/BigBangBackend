# Gunicorn configuration file
import multiprocessing

# Increase timeout to 300 seconds (5 minutes)
timeout = 300

# Worker settings
workers = multiprocessing.cpu_count() * 2 + 1
threads = 2
worker_class = 'gthread'

# Keep the application alive
keepalive = 65

# Log settings
accesslog = '-'  # Log to stdout
errorlog = '-'   # Log errors to stdout
loglevel = 'info'

# SSL settings
certfile = None
keyfile = None

# Worker process name
proc_name = 'bigbangbackend'

# Prevent worker timeouts on slow tasks
graceful_timeout = 300

# Preload application for better performance
preload_app = True