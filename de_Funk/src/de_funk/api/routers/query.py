"""POST /api/query — registry-based dispatch to exhibit handlers."""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from de_funk.config.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post("/query")
async def execute_query(payload: dict, request: Request) -> Any:
    """Execute a de_funk block query via the handler registry."""
    t_start = time.perf_counter()

    block_type = payload.get("type", "")
    if not block_type:
        raise HTTPException(status_code=400, detail="'type' field is required")

    filters_summary = [(f.get('field'), f.get('operator'), f.get('value')) for f in (payload.get('filters') or []) if isinstance(f, dict)]
    logger.info(f"Query: type={block_type}, rows={payload.get('rows')}, cols={payload.get('cols')}, measures={[m.get('key') if isinstance(m, dict) else m for m in (payload.get('measures') or [])]}, filters={filters_summary}")

    handler = request.app.state.registry.get(block_type)
    if not handler:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown block type '{block_type}'. See exhibits/_index.md for valid types.",
        )

    resolver = request.app.state.resolver

    try:
        result = handler.execute(payload, resolver)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        elapsed = (time.perf_counter() - t_start) * 1000
        logger.error(f"Query FAILED type={block_type} ({elapsed:.0f}ms): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")

    elapsed = (time.perf_counter() - t_start) * 1000
    logger.info(f"Query OK type={block_type} ({elapsed:.0f}ms)")
    return result
