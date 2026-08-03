# Gunicorn config for agriTwin web service.
#
# Worker formula: min((2 × OCPUs) + 1, 3) processes, 4 threads each.
#
# The original (2×OCPUs)+1 formula (still workers=9 on this box's 4 OCPUs)
# assumed a dedicated Postgres instance. In production this app shares a
# connection-constrained TimescaleDB instance with another app
# (max_connections=25 total -- see SERVER_SETUP.md), and each gunicorn
# WORKER PROCESS opens its own SQLAlchemy pool (agritwin_app/db/session.py)
# -- more processes means more independent pools competing for the same
# tiny connection budget. This was the actual cause of two separate
# "remaining connection slots reserved for SUPERUSER" production incidents:
# the first (see post_fork below) was a fork-safety bug that leaked
# connections outright; even after fixing that, 9 correctly-bounded pools
# still added up to more baseline idle connections than the shared instance
# could spare on a low-traffic app where most pooled connections, once
# opened, rarely get reused often enough to hit pool_recycle.
#
# The app is Postgres I/O-bound, not CPU-bound (gthread worker class) --
# trading worker processes for threads doesn't cost concurrency, since
# threads within one process share a single pool instead of each opening
# their own. Capped at 3 processes regardless of OCPU count, with more
# threads per process to compensate.

import multiprocessing

workers = min((2 * multiprocessing.cpu_count()) + 1, 3)
worker_class = "gthread"
threads = 4
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
