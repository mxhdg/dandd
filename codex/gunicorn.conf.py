bind = "0.0.0.0:5000"

# This serves one D&D table's character sheets, not internet-scale traffic:
# a couple of small worker processes with a few threads each easily covers
# several players hitting Save around the same time.
workers = 2
worker_class = "gthread"
threads = 4
timeout = 30
graceful_timeout = 30
keepalive = 5

max_requests = 500
max_requests_jitter = 50
preload_app = True

accesslog = "-"
errorlog = "-"
loglevel = "info"
