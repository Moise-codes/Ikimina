"""Gunicorn configuration for running the API in a container.

Gunicorn supervises the processes; each worker runs the Uvicorn ASGI server via
``uvicorn_worker.UvicornWorker``. Every value can be overridden with an
environment variable so the same image works from a laptop to production.
"""

from __future__ import annotations

import multiprocessing
import os

bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")
workers = int(os.getenv("GUNICORN_WORKERS", str(multiprocessing.cpu_count() * 2 + 1)))
worker_class = "uvicorn_worker.UvicornWorker"
timeout = int(os.getenv("GUNICORN_TIMEOUT", "60"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))

accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")

# Only trust X-Forwarded-* headers from a local reverse proxy; set this to the
# proxy address in production. See the deployment notes/docs.
forwarded_allow_ips = os.getenv("FORWARDED_ALLOW_IPS", "127.0.0.1")
