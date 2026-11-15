# Ikimina

Backend API for managing community savings and lending groups (*ibimina*) in Rwanda.
Members save together, the group lends to its members, and every movement of money is
recorded in a tamper-proof ledger.

This repository is a **monorepo**:

```
Ikimina/
├── backend/     # The API (this is what we build now)
├── frontend/    # Placeholder; the owner builds it later
├── docs/        # Design document, architecture decisions (ADRs), runbooks
└── docker-compose.yml   # PostgreSQL, Redis (and later api + worker)
```

## Status

- **Phase 0 (Foundation):** done — monorepo layout, fail-fast typed configuration,
  SQLAlchemy 2.0 core + Alembic, FastAPI app factory with middleware and a
  consistent error envelope, health/readiness probes, Docker image, Docker Compose
  and CI.
- Next: Phase 1 (identity and authentication).

## Documentation

- Design document (source of truth): [`docs/ikimina-v2-design.md`](docs/ikimina-v2-design.md)
- Backend developer guide: [`backend/README.md`](backend/README.md)

## Quick start

Requires Python 3.12+ (the code also runs on newer versions), Docker, and Docker Compose.

```bash
# 1. Create and activate a virtual environment (venv + pip only, never uv)
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r backend/requirements-dev.txt

# 3. Create your local environment file from the template
cp .env.example .env
#    then edit .env: set strong SECRET_KEY and ENCRYPTION_KEY values

# 4. Start PostgreSQL and Redis
docker compose up -d

# 5. Run the API in development (from the backend folder)
cd backend
uvicorn app.main:app --reload
```

See [`backend/README.md`](backend/README.md) for the full developer guide (tests,
migrations, checks).
