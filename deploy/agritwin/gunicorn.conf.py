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


def post_fork(server, worker):
    # preload_app=True above means the Flask app factory (and the SQLAlchemy
    # engine it creates via init_db()) runs once in this master process
    # before forking -- every worker below otherwise inherits the master's
    # already-open pooled connections via fork() instead of opening its own.
    # This is SQLAlchemy's documented fork-safety hazard ("Using Connection
    # Pools with Multiprocessing or os.fork()") and is what caused idle
    # connections to leak and accumulate for days, eventually exhausting the
    # shared TimescaleDB instance's connection cap. dispose_engine(close=False)
    # discards the inherited pool without closing the underlying sockets out
    # from under the master/sibling workers that share the same inherited
    # file descriptors -- this worker then opens fresh, worker-owned
    # connections on next use. See agritwin_app/db/session.py's own comment.
    from agritwin_app.db.session import dispose_engine

    dispose_engine(close=False)
