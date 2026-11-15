"""The aggregate router for ``/api/v1``.

Domain routers (auth, groups, memberships, ledger, payments, loans, reports) are
attached here in later phases. Keeping one aggregate router means ``main`` only
has to know about the prefix, not about every domain module.
"""

from __future__ import annotations

from fastapi import APIRouter

api_router = APIRouter()
