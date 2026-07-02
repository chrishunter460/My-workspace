"""
Bronze layer API routes — query, dimensions, and catalog for raw Bronze data.

Reuses the same handler registry as Silver (PivotHandler, GraphicalHandler, etc.)
by swapping in BronzeResolver instead of FieldResolver. All exhibit types work
unchanged against Bronze data.
"""
from __future__ import annotations

import json
import time
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import ValidationError

from de_funk.api.models.requests import DimensionValuesResponse
from de_funk.config.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["bronze"])


@router.post("/bronze/query")
async def bronze_query(payload: dict, request: Request) -> Any:
    """Execute a de_funk block query against Bronze data."""
    t_start = time.perf_counter()

    block_type = payload.get("type", "")
    if not block_type:
        raise HTTPException(status_code=400, detail="'type' field is required")

    filters_summary = [
        (f.get("field"), f.get("operator"), f.get("value"))
        for f in (payload.get("filters") or [])
        if isinstance(f, dict)
    ]
    logger.info(
        f"Bronze query: type={block_type}, "
        f"rows={payload.get('rows')}, cols={payload.get('cols')}, "
        f"measures={[m.get('key') if isinstance(m, dict) else m for m in (payload.get('measures') or [])]}, "
        f"filters={filters_summary}"
    )

    handler = request.app.state.registry.get(block_type)
    if not handler:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown block type '{block_type}'. See exhibits/_index.md for valid types.",
        )

    bronze_resolver = request.app.state.bronze_resolver

    try:
        result = handler.execute(payload, bronze_resolver)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        elapsed = (time.perf_counter() - t_start) * 1000
        logger.error(
            f"Bronze query FAILED type={block_type} ({elapsed:.0f}ms): {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")

    elapsed = (time.perf_counter() - t_start) * 1000
    logger.info(f"Bronze query OK type={block_type} ({elapsed:.0f}ms)")
    return result


@router.get(
    "/bronze/dimensions/{ref:path}",
    response_model=DimensionValuesResponse,
)
async def bronze_dimension_values(
    ref: str,
    request: Request,
    order_by: Optional[str] = Query(
        None,
        description="provider.endpoint.field to order values by",
    ),
    order_dir: str = Query("desc", description="asc or desc"),
    filters: Optional[str] = Query(
        None,
        description='JSON array of context filters, e.g. [{"field":"chicago.crimes.year","value":[2023]}]',
    ),
) -> DimensionValuesResponse:
    """Return distinct values for a Bronze field — used by filter dropdowns."""
    t_start = time.perf_counter()
    ref_str = ref.replace("/", ".")
    bronze_resolver = request.app.state.bronze_resolver
    executor = request.app.state.executor

    try:
        resolved = bronze_resolver.resolve(ref_str)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Parse context filters
    extra_filters: list[tuple[Any, Any]] | None = None
    if filters:
        try:
            raw_filters: list[dict] = json.loads(filters)
            extra_filters = []
            for f in raw_filters:
                f_field = f.get("field", "")
                f_val = f.get("value")
                if not f_field or f_val is None:
                    continue
                try:
                    f_resolved = bronze_resolver.resolve(f_field)
                    extra_filters.append((f_resolved, f_val))
                except ValueError:
                    pass
        except (json.JSONDecodeError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid filters JSON")

    try:
        if order_by:
            order_resolved = bronze_resolver.resolve(order_by)
            values = executor.distinct_values_by_measure(
                resolved, order_resolved, order_dir, extra_filters, bronze_resolver
            )
        else:
            values = executor.distinct_values(
                resolved, extra_filters, bronze_resolver
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")

    elapsed = (time.perf_counter() - t_start) * 1000
    logger.info(f"Bronze dimensions OK {ref_str} ({elapsed:.0f}ms) → {len(values)} values")
    return DimensionValuesResponse(field=ref_str, values=values)


@router.get("/bronze/endpoints")
async def bronze_endpoints(request: Request) -> dict:
    """Return the Bronze endpoint catalog — providers, endpoints, and fields."""
    bronze_resolver = request.app.state.bronze_resolver
    return bronze_resolver.get_endpoint_catalog()
