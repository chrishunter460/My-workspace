"""GET /api/domains — return the full field catalog for all domains."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

router = APIRouter()


@router.get("/domains")
async def get_domains(request: Request) -> dict:
    """Return the field catalog: {domain: {field: {table, column, format}}}."""
    resolver = request.app.state.resolver
    return resolver.get_field_catalog()
