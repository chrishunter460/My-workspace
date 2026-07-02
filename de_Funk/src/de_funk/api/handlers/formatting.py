"""Shared formatting utilities for all exhibit handlers.

Provides format code resolution, color mapping, and parsing of the
declarative ``formatting`` section from YAML exhibit blocks.

Format codes available::

    $       $1,234          Whole dollars
    $2      $1,234.56       Dollars + cents
    $K      $1.2K           Thousands
    $M      $1.2M           Millions
    $B      $1.23B          Billions
    %       12.34%          Percent (2 decimals)
    %0      12%             Percent (whole)
    number  1,234           Integer with separators
    decimal 1.2345          4 decimal places
    decimal2 1.23           2 decimal places
"""
from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Format code registry — used by GT formatter and client-side renderers
# ---------------------------------------------------------------------------

FORMAT_CODES: dict[str, dict[str, Any]] = {
    "$":        {"type": "currency", "currency": "USD", "decimals": 0},
    "$2":       {"type": "currency", "currency": "USD", "decimals": 2},
    "$K":       {"type": "number",   "decimals": 1, "scale": 1e-3, "suffix": "K", "prefix": "$"},
    "$M":       {"type": "number",   "decimals": 1, "scale": 1e-6, "suffix": "M", "prefix": "$"},
    "$B":       {"type": "number",   "decimals": 2, "scale": 1e-9, "suffix": "B", "prefix": "$"},
    "%":        {"type": "percent",  "decimals": 2},
    "%0":       {"type": "percent",  "decimals": 0},
    "number":   {"type": "number",   "decimals": 0, "separators": True},
    "decimal":  {"type": "number",   "decimals": 4, "separators": False},
    "decimal2": {"type": "number",   "decimals": 2, "separators": False},
}

# Default colors by column kind
DEFAULT_COLORS = {
    "measure": None,            # no default fill for measures
    "window":  "#fff8e1",       # light yellow for window calculations
    "totals":  "#f5f5f5",       # light grey for totals rows
}


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_format_section(format_section: dict | None) -> dict[str, dict]:
    """Parse the ``format`` dict from a formatting block.

    Supports two forms::

        format:
          avg_close: {format: $, color: "#e3f2fd"}   # full
          total_vol: number                            # short (format only)

    Returns ``{key: {"format": str|None, "color": str|None}}``.
    """
    if not format_section or not isinstance(format_section, dict):
        return {}
    result: dict[str, dict] = {}
    for key, spec in format_section.items():
        if isinstance(spec, dict):
            result[key] = {
                "format": spec.get("format"),
                "color": spec.get("color"),
            }
        elif isinstance(spec, str):
            result[key] = {"format": spec, "color": None}
    return result


def resolve_format(
    key: str,
    column_format: str | None,
    overrides: dict[str, dict],
) -> str | None:
    """Resolve effective format code for a column.

    Priority: formatting.format override > column-level format > None.
    """
    override = overrides.get(key, {})
    return override.get("format") or column_format


def resolve_color(
    key: str,
    kind: str,
    overrides: dict[str, dict],
    defaults: dict[str, Any] | None = None,
) -> str | None:
    """Resolve effective color for a column.

    Priority: formatting.format[key].color > defaults by kind > None.
    """
    defaults = defaults or {}
    override = overrides.get(key, {})
    color = override.get("color")
    if not color:
        if kind == "window":
            color = defaults.get("window_color", DEFAULT_COLORS["window"])
        elif kind == "measure":
            color = defaults.get("measure_color", DEFAULT_COLORS["measure"])
    return color
