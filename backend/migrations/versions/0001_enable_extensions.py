"""enable citext and pgcrypto extensions

``citext`` gives us case-insensitive e-mail uniqueness; ``pgcrypto`` provides
``gen_random_uuid()``/hashing helpers used by later migrations and defaults.

Revision ID: 0001
Revises:
Create Date: 2026-11-15
"""

from __future__ import annotations

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
    op.execute("DROP EXTENSION IF EXISTS citext")
