# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1 - builder.
# Installs the runtime dependencies into a self-contained virtual environment.
# Anything a package needs at build time (compilers, headers) stays here and is
# not present in the final image.
# ---------------------------------------------------------------------------
FROM python:3.15-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install --requirement requirements.txt

# ---------------------------------------------------------------------------
# Stage 2 - runtime.
# Only the virtual environment and the application code; no compilers, no
# package caches, and it runs as an unprivileged user.
# ---------------------------------------------------------------------------
FROM python:3.15-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Dedicated system account; --create-home gives it a writable HOME if needed.
RUN groupadd --system app \
    && useradd --system --gid app --home-dir /app --create-home app

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=app:app alembic.ini gunicorn.conf.py ./
COPY --chown=app:app migrations ./migrations
COPY --chown=app:app app ./app

USER app
EXPOSE 8000

# Liveness check that needs no extra packages (no curl in the slim image).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)"]

# Gunicorn supervises Uvicorn workers; see gunicorn.conf.py for the settings.
CMD ["gunicorn", "app.main:app", "--config", "gunicorn.conf.py"]
