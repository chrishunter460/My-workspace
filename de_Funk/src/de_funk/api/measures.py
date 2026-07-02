"""
Measure SQL generation — translates MeasureTuple configs into SQL expressions.

Separates base aggregation measures (SUM, AVG, COUNT) from window functions
(delta, pct_delta, share) that require a second CTE pass.
"""
from __future__ import annotations

from typing import Any

# Computation catalog — maps fn keys to SQL templates
_FN_TEMPLATES: dict[str, str] = {
    "divide":    "{a} / NULLIF({b}, 0)",
    "rate":      "{events} / NULLIF({exposed}, 0)",
    "subtract":  "{from_} - {subtract}",
    "add":       " + ".join(["{fields}"]),  # expanded in _resolve_fn
    "multiply":  "{a} * {by}",
    "delta":     "{of} - LAG({of}) OVER (ORDER BY 1)",
    "pct_delta": "({of} - LAG({of}) OVER (ORDER BY 1)) / NULLIF(LAG({of}) OVER (ORDER BY 1), 0)",
    "share":     "{of} / NULLIF(SUM({total}) OVER (), 0)",
}

# Functions that require a window pass (LAG, running aggregates)
_WINDOW_FNS = {"delta", "pct_delta", "share"}


def is_window_fn(field: object) -> bool:
    """Return True if a measure field uses a window function."""
    if isinstance(field, dict):
        return field.get("fn") in _WINDOW_FNS
    return False


def _resolve_fn(fn_config: dict, prior_keys: dict[str, str]) -> str:
    """Translate a computation function config to a SQL expression."""
    fn = fn_config.get("fn")
    if fn not in _FN_TEMPLATES:
        raise ValueError(f"Unknown computation function '{fn}'. See exhibits/_base/computations.md.")

    if fn == "add":
        fields = fn_config.get("fields", [])
        parts = [prior_keys.get(f, f) for f in fields]
        return " + ".join(parts)

    template = _FN_TEMPLATES[fn]
    kwargs: dict[str, str] = {}
    for param_key, param_val in fn_config.items():
        if param_key == "fn":
            continue
        sql_key = "from_" if param_key == "from" else param_key
        kwargs[sql_key] = prior_keys.get(param_val, param_val)

    return template.format(**kwargs)


def build_measure_sql(
    measure,
    resolver: Any,
    prior_keys: dict[str, str],
) -> str:
    """Build the SQL expression for a single measure tuple.

    Args:
        measure: MeasureTuple with key, field, aggregation, format, label.
        resolver: FieldResolver for domain.field → table.column resolution.
        prior_keys: Map of previously resolved measure keys → SQL expressions,
                    used for chained computations (e.g. divide referencing prior measures).
    """
    field = measure.field

    if isinstance(field, dict):
        return _resolve_fn(field, prior_keys)

    resolved = resolver.resolve(field)
    col = f'"{resolved.table_name}"."{resolved.column}"'

    if measure.aggregation:
        agg = measure.aggregation.upper()
        if agg == "COUNT_DISTINCT":
            return f"COUNT(DISTINCT {col})"
        return f"{agg}({col})"

    return col
