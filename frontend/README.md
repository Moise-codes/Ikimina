# Ikimina Frontend (placeholder)

This folder is intentionally empty for now. The web/mobile frontend will be added
later by the owner. The backend is built first and lives in [`../backend`](../backend).

The backend is designed to be frontend-friendly:

- All routes are versioned under `/api/v1`.
- Consistent JSON envelopes for success and errors.
- CORS is controlled by an explicit allow-list in settings (no wildcard with credentials).
- An OpenAPI schema is generated automatically (enabled only in local/dev).

Do not add frontend code in this phase.
