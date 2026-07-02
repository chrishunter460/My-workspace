"""GET /api/dimensions/{ref} — return distinct values for a domain.field (for sidebar dropdowns)."""
from __future__ import annotations

import json
import time
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from de_funk.api.models.requests import DimensionValuesResponse
from de_funk.config.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/dimensions/{ref:path}", response_model=DimensionValuesResponse)
async def get_dimension_values(
    ref: str,
    request: Request,
    order_by: Optional[str] = Query(None, description="domain.field to order values by (e.g. stocks.market_cap)"),
    order_dir: str = Query("desc", description="asc or desc"),
    filters: Optional[str] = Query(None, description='JSON array of {field, value} context filters, e.g. [{"field":"corporate.entity.sector","value":["TECHNOLOGY"]}]'),
) -> DimensionValuesResponse:
    """Return distinct values for a field reference — used by sidebar filter dropdowns."""
    t_start = time.perf_counter()
    ref_str = ref.replace("/", ".")
    resolver = request.app.state.resolver
    executor = request.app.state.executor

    try:
        resolved = resolver.resolve(ref_str)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Parse context filters — [{field: "domain.field", value: ...}] → [(ResolvedField, value)]
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
                    f_resolved = resolver.resolve(f_field)
                    extra_filters.append((f_resolved, f_val))
                except ValueError:
                    pass  # Unknown field — skip rather than error
        except (json.JSONDecodeError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid filters JSON")

    try:
        if order_by:
            order_resolved = resolver.resolve(order_by)
            values = executor.distinct_values_by_measure(
                resolved, order_resolved, order_dir, extra_filters, resolver
            )
        else:
            values = executor.distinct_values(resolved, extra_filters, resolver)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")

    elapsed = (time.perf_counter() - t_start) * 1000
    logger.info(f"Dimensions OK {ref_str} ({elapsed:.0f}ms) → {len(values)} values")
    return DimensionValuesResponse(field=ref_str, values=values)
