# Gunicorn config for agriTwin web service.
#
# Worker formula: (2 × OCPUs) + 1
#
#   1 OCPU / 6 GB RAM  → workers=3, threads=2  (~360 MB peak with preload)
#   4 OCPU / 24 GB RAM → workers=9, threads=2
#
# The app is Postgres I/O-bound, not CPU-bound. gthread worker class lets each
# worker handle concurrent requests without spawning extra processes.

import multiprocessing

workers = (2 * multiprocessing.cpu_count()) + 1
worker_class = "gthread"
threads = 2
bind = "0.0.0.0:5000"
timeout = 120
graceful_timeout = 30
accesslog = "-"
errorlog = "-"
loglevel = "info"
# Share app state across workers — saves ~80 MB on the 1-OCPU config.
preload_app = True
# Restart workers periodically to prevent memory growth from Pandas operations.
max_requests = 500
max_requests_jitter = 50
