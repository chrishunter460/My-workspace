"""Pivot reshape utilities — column key construction and 1D window calculations.

Column keys use ``||`` as separator so Great Tables can derive spanners
and labels by splitting on ``||``.

The 2D pivot cross-product is now handled entirely in DuckDB via
conditional aggregation (see pivot.py:_query_2d_wide). Only the 1D
window helper and shared key utilities remain here.
"""
from __future__ import annotations

import re

from de_funk.api.models.requests import TableColumn, WindowSpec


def _sort_key(val) -> tuple:
    """Numeric-first sort key for mixed string/number dimension values.

    Handles ``||``-separated keys by sorting on each part independently
    so ``"2020||TECHNOLOGY"`` sorts by (2020, "TECHNOLOGY").
    """
    s = str(val)
    parts = s.split("||") if "||" in s else [s]
    key: list = []
    for part in parts:
        first = re.split(r'[-~>=]', part.strip())[0].strip()
        try:
            key.extend([0, float(first)])
        except ValueError:
            key.extend([1, part.strip()])
    return tuple(key)


def _col_name(val: str, alias: str, layout: str) -> str:
    """Canonical wide-column name: alias||val (by_measure) or val||alias (by_column)."""
    return f"{val}||{alias}" if layout == "by_column" else f"{alias}||{val}"


# ---------------------------------------------------------------------------
# Window calculations on 1D pivot rows (no column dimension)
# ---------------------------------------------------------------------------

def apply_windows_1d(
    rows: list[list],
    columns: list[TableColumn],
    windows: list[WindowSpec],
) -> tuple[list[list], list[TableColumn]]:
    """Apply row-over-row window calculations to a 1D (flat) pivot."""
    col_index = {c.key: i for i, c in enumerate(columns)}
    for win in windows:
        src_idx = col_index.get(win.source)
        if src_idx is None:
            continue
        new_col = []
        for i, row in enumerate(rows):
            val = row[src_idx]
            prev = rows[i - 1][src_idx] if i > 0 else None
            if win.type == "pct_change":
                if prev and val is not None and prev != 0:
                    new_col.append(round((val - prev) / prev, 4))
                else:
                    new_col.append(None)
            elif win.type == "diff":
                if prev is not None and val is not None:
                    new_col.append(val - prev)
                else:
                    new_col.append(None)
            else:
                new_col.append(None)
        for i, row in enumerate(rows):
            row.append(new_col[i])
        columns.append(TableColumn(
            key=win.key,
            label=win.label or win.key.replace("_", " ").title(),
            format="%",
        ))
        col_index[win.key] = len(columns) - 1
    return rows, columns
