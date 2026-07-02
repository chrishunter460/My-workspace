"""
Query utilities — helper functions for exhibit handlers.

The QueryEngine class has been removed. Handlers now use Engine directly
via the _engine attribute injected by HandlerRegistry.

Remaining utilities:
    _eval_date_expr: Evaluate frontmatter date expressions
    truncate_to_mb: Cap response size for JSON serialization
"""
from __future__ import annotations

import re
from datetime import date, timedelta


def _eval_date_expr(expr: object) -> str | None:
    """Evaluate frontmatter date expressions to ISO date strings.

    Handles: current_date, current_date ± N, year_start, literal dates.
    """
    if expr is None:
        return None
    s = str(expr).strip()
    today = date.today()
    if s == "current_date":
        return str(today)
    m = re.match(r"current_date\s*-\s*(\d+)", s)
    if m:
        return str(today - timedelta(days=int(m.group(1))))
    m = re.match(r"current_date\s*\+\s*(\d+)", s)
    if m:
        return str(today + timedelta(days=int(m.group(1))))
    if s == "year_start":
        return str(today.replace(month=1, day=1))
    return s


def truncate_to_mb(rows: list[list], columns, max_mb: float) -> tuple[list[list], bool]:
    """Truncate row list so the JSON-serialised response stays under max_mb.

    Returns (rows, truncated).  Uses a fast byte estimate from a 50-row sample.
    """
    import json
    max_bytes = int(max_mb * 1024 * 1024)
    if not rows:
        return rows, False
    sample = rows[:min(50, len(rows))]
    sample_bytes = len(json.dumps(sample, default=str).encode())
    bytes_per_row = sample_bytes / len(sample)
    estimated_total = bytes_per_row * len(rows)
    if estimated_total <= max_bytes:
        return rows, False
    max_rows = max(1, int(max_bytes / bytes_per_row))
    return rows[:max_rows], True
