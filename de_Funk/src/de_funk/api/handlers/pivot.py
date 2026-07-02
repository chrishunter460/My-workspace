"""PivotHandler — single exhibit handler for all pivot table queries.

Always renders via Great Tables. Supports:
  - 1D pivot (rows only, measures as flat columns)
  - 2D pivot (rows + cols) via SQL conditional aggregation:
      by_measure: spanners = measure labels, sub-cols = dimension values
      by_column:  spanners = dimension values, sub-cols = measure labels
      by_dimension: single measure, flat columns (no spanners)
  - Multiple row/col fields (multi-level GROUP BY)
  - Totals via GROUPING SETS (row totals, col totals)
  - Expandable hierarchical pivots: subtotals rendered as HTML, detail
    rows sent as JSON for client-side expand/collapse
  - Sort by resolved field (e.g. sort: {field: corporate.finance.display_order, dir: asc})
  - Window calculations (yoy, diff) via DuckDB LAG() on both 1D and 2D
"""
from __future__ import annotations

from typing import Any

from de_funk.api.executor import truncate_to_mb
from de_funk.api.handlers.base import ExhibitHandler
from de_funk.api.handlers.reshape import (
    _col_name,
    apply_windows_1d,
)
from de_funk.api.measures import build_measure_sql, is_window_fn
from de_funk.api.models.requests import (
    PivotQueryRequest,
    TableColumn,
    TableResponse,
)
from de_funk.api.resolver import FieldResolver
from de_funk.config.logging import get_logger

logger = get_logger(__name__)

# Maximum rows rendered as HTML. Beyond this, the pivot becomes
# hierarchical: subtotals are rendered, detail rows sent as JSON.
MAX_HTML_ROWS = 400

# Maximum distinct column combinations before the wide query is generated.
# Prevents runaway SQL and GT rendering on unfiltered pivots.
MAX_PIVOT_COLUMNS = 200


class PivotHandler(ExhibitHandler):
    handles = {"table.pivot", "pivot", "pivot_table"}

    def execute(self, payload: dict[str, Any], resolver: FieldResolver) -> TableResponse:
        req = PivotQueryRequest(**payload)

        # Resolve all row fields
        row_resolved = [resolver.resolve(f) for f in req.row_fields]
        row_exprs = [f'"{r.table_name}"."{r.column}"' for r in row_resolved]
        # Use GROUPING() to distinguish subtotal NULLs from real data NULLs.
        # GROUPING(expr) = 1 when NULL is from GROUPING SETS, 0 when it's real data.
        has_totals = req.totals and req.totals.rows
        if has_totals:
            row_select_exprs = [
                f"CASE WHEN GROUPING({e}) = 1 THEN 'Total' ELSE CAST({e} AS VARCHAR) END"
                for e in row_exprs
            ]
        else:
            row_select_exprs = [f"CAST({e} AS VARCHAR)" for e in row_exprs]

        # Resolve all col fields
        col_resolved = [resolver.resolve(f) for f in req.col_fields]
        col_exprs = [f'"{c.table_name}"."{c.column}"' for c in col_resolved]
        col_select_exprs = [f"COALESCE(CAST({e} AS VARCHAR), 'TOTAL')" for e in col_exprs]

        # Build measure SQL
        prior_keys: dict[str, str] = {}
        measure_exprs = []
        for m in req.measures:
            expr = build_measure_sql(m, resolver, prior_keys)
            prior_keys[m.key] = expr
            measure_exprs.append((m, expr))

        str_field_tables = [
            resolver.resolve(m.field) for m in req.measures
            if isinstance(m.field, str)
        ]
        # Resolve sort — supports:
        #   sort: {field: "domain.field", dir: "asc"}               (sort by a dimension field)
        #   sort: {by: "incidents", where: "2025", order: "desc"}   (sort by measure value at a column)
        sort_resolved = None
        sort_tables = []
        sort_direction = "ASC"
        sort_by_measure = None  # (measure_key, col_value) for pivot-specific sort
        raw_sort = payload.get("sort") or payload.get("data", {}).get("sort")
        if raw_sort and isinstance(raw_sort, dict):
            sort_direction = (raw_sort.get("dir") or raw_sort.get("order") or "asc").upper()

            if "by" in raw_sort and "where" in raw_sort:
                # Pivot measure sort: sort rows by a measure's value at a specific column
                sort_by_measure = (raw_sort["by"], str(raw_sort["where"]))
            else:
                sort_field = raw_sort.get("field") or (raw_sort.get("rows", {}) or {}).get("by")
                if sort_field:
                    sort_resolved = resolver.resolve(sort_field)
                    sort_tables = [sort_resolved]

        # Build core tables first, then resolve filter tables with domain scoping
        core_fields = row_resolved + col_resolved + str_field_tables + sort_tables
        core_tables, core_domains = self._collect_tables_with_domains(core_fields)
        allowed = resolver.reachable_domains(core_domains)
        filter_tables = self._resolve_filter_tables(
            req.filters, resolver, allowed_domains=allowed,
        )
        tables = self._collect_tables(core_fields + filter_tables)
        from_clause = self._build_from(tables, resolver, allowed_domains=allowed)
        where_clauses = self._build_where(req.filters, resolver)
        where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        # Sort clause — the raw sort expression (without ORDER BY prefix)
        sort_expr_raw = ""
        if sort_by_measure:
            measure_key, col_value = sort_by_measure
            for m, expr in measure_exprs:
                if m.key == measure_key:
                    if col_exprs:
                        col_filter = " AND ".join(
                            f"{ce} = '{col_value}'" for ce in col_exprs
                        )
                        sort_expr_raw = f"{expr} FILTER (WHERE {col_filter}) {sort_direction}"
                    else:
                        sort_expr_raw = f"{expr} {sort_direction}"
                    break
            if not sort_expr_raw:
                logger.warning(f"Sort measure '{measure_key}' not found in measures")
        elif sort_resolved:
            sort_expr_raw = f'MIN("{sort_resolved.table_name}"."{sort_resolved.column}") {sort_direction}'

        # Build ORDER BY with TOTAL rows anchored at the bottom of each group.
        # For N row keys, generate CASE WHEN guards that push "TOTAL" values
        # to sort last at each nesting level, then apply the user's sort.
        n_rows = len(row_exprs)
        anchor_parts = []
        for i in range(n_rows):
            anchor_parts.append(f"CASE WHEN row_key_{i} = 'TOTAL' THEN 1 ELSE 0 END")
            if i < n_rows - 1:
                anchor_parts.append(f"row_key_{i}")

        if sort_expr_raw:
            anchor_parts.append(sort_expr_raw)
        else:
            anchor_parts.append(f"row_key_{n_rows - 1}")

        sort_clause = f"ORDER BY {', '.join(anchor_parts)}"

        logger.info(f"Pivot: rows={req.row_fields}, cols={req.col_fields}, measures=[{', '.join(m.key for m in req.measures)}]")

        if col_resolved:
            row_list, columns = self._query_2d_wide(
                req, row_exprs, col_exprs, measure_exprs,
                from_clause, where_clause, sort_clause,
            )
        else:
            row_list, columns = self._query_1d(
                req, row_exprs, measure_exprs,
                from_clause, where_clause, sort_clause,
            )

        # Remove duplicate TOTAL rows (NULL grouping produces extra zero-sum totals)
        total_rows = [r for r in row_list if r[0] == "TOTAL"]
        if len(total_rows) > 1:
            # Keep only the TOTAL row with the highest sum (the real total)
            best_total = max(total_rows, key=lambda r: sum(v for v in r[1:] if isinstance(v, (int, float))))
            row_list = [r for r in row_list if r[0] != "TOTAL"] + [best_total]

        row_list, truncated = truncate_to_mb(row_list, columns, self.max_response_mb)
        if truncated:
            logger.info(f"Pivot response truncated to {len(row_list)} rows ({self.max_response_mb}MB cap)")

        # Return raw data for AG Grid rendering (no Great Tables HTML)
        return TableResponse(
            columns=columns,
            rows=row_list,
            truncated=truncated,
            formatting=payload.get("formatting"),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _row_labels(self, fields: list[str]) -> list[str]:
        """Generate display labels from dotted field names."""
        return [f.split(".")[-1].replace("_", " ").title() for f in fields]

    def _totals_sql(self, row_exprs, col_exprs, has_totals) -> str:
        """Build GROUPING SETS clause for totals rows (1D path)."""
        if not has_totals:
            return ", ".join(row_exprs + col_exprs)

        all_dims = row_exprs + col_exprs
        sets = [f"({', '.join(all_dims)})"]  # detail rows

        if has_totals:
            sets.append("()")
            for i in range(len(row_exprs) - 1):
                sets.append(f"({', '.join(row_exprs[:i + 1] + col_exprs)})")

        return f"GROUPING SETS ({', '.join(sets)})"

    def _totals_sql_rows_only(self, row_exprs, has_totals) -> str:
        """Build GROUPING SETS for row dimensions only (2D wide path).

        Column dimensions are handled by FILTER clauses, so GROUPING SETS
        only needs to roll up row dimensions.
        """
        if not has_totals:
            return ", ".join(row_exprs)

        sets = [f"({', '.join(row_exprs)})"]  # detail rows
        sets.append("()")  # grand total
        for i in range(len(row_exprs) - 1):
            sets.append(f"({', '.join(row_exprs[:i + 1])})")  # subtotals

        return f"GROUPING SETS ({', '.join(sets)})"

    # ------------------------------------------------------------------
    # 2D wide pivot helpers
    # ------------------------------------------------------------------

    def _discover_col_values(self, col_exprs, from_clause, where_clause):
        """Pre-query: discover distinct column value combinations.

        Returns sorted list of tuples, e.g. [(2020, 'TECH'), (2020, 'FIN'), ...].
        Raises ValueError if the cross-product exceeds MAX_PIVOT_COLUMNS.
        """
        select_parts = [f"{expr} AS cv_{i}" for i, expr in enumerate(col_exprs)]
        order_parts = [f"cv_{i}" for i in range(len(col_exprs))]

        sql = f"""
            SELECT DISTINCT {', '.join(select_parts)}
            FROM {from_clause}
            {where_clause}
            ORDER BY {', '.join(order_parts)}
        """
        logger.debug(f"Pivot pre-query (col discovery): {sql}")
        combos = self._execute(sql, max_rows=MAX_PIVOT_COLUMNS + 1)

        # Filter out combos with NULL values (e.g. crimes with no year)
        combos = [c for c in combos if all(v is not None for v in c)]

        if len(combos) > MAX_PIVOT_COLUMNS:
            raise ValueError(
                f"Pivot column cross-product has {len(combos)}+ unique combinations "
                f"(max {MAX_PIVOT_COLUMNS}). Add filters to reduce column dimensions."
            )
        return combos

    @staticmethod
    def _combo_to_key(combo: tuple) -> str:
        """Convert a column combination tuple to a ``||``-separated key string.

        Single-element: (2020,) → "2020"
        Multi-element:  (2020, "TECHNOLOGY") → "2020||TECHNOLOGY"
        """
        parts = [str(v) if v is not None else "(null)" for v in combo]
        if len(parts) > 1:
            return f"{parts[0]}||{' | '.join(parts[1:])}"
        return parts[0]

    @staticmethod
    def _filter_clause(col_exprs: list[str], combo: tuple) -> str:
        """Build a FILTER WHERE clause for one column combination."""
        parts = []
        for expr, val in zip(col_exprs, combo):
            if val is None:
                parts.append(f"{expr} IS NULL")
            elif isinstance(val, str):
                escaped = val.replace("'", "''")
                parts.append(f"{expr} = '{escaped}'")
            else:
                parts.append(f"{expr} = {val}")
        return " AND ".join(parts)

    def _measure_combo_pairs(
        self,
        measure_exprs: list[tuple],
        combos: list[tuple],
        layout: str,
    ) -> list[tuple[tuple, str, tuple]]:
        """Return (measure_tuple_pair, combo_str, combo) in layout-correct order.

        The ordering must match _build_wide_columns so SQL SELECT columns
        align with the metadata:
          by_column/by_dimension: combos (outer) × measures (inner)
          by_measure:             measures (outer) × combos (inner)
        """
        pairs = []
        combo_strs = [(c, self._combo_to_key(c)) for c in combos]

        if layout in ("by_column", "by_dimension"):
            for combo, cs in combo_strs:
                for m_pair in measure_exprs:
                    pairs.append((m_pair, cs, combo))
        else:  # by_measure
            for m_pair in measure_exprs:
                for combo, cs in combo_strs:
                    pairs.append((m_pair, cs, combo))
        return pairs

    def _generate_wide_sql(
        self,
        row_exprs: list[str],
        col_exprs: list[str],
        measure_exprs: list[tuple],
        combos: list[tuple],
        layout: str,
        from_clause: str,
        where_clause: str,
        group_clause: str,
        sort_clause: str,
        windows: list | None,
    ) -> str:
        """Generate wide SQL with conditional aggregation.

        For each (combo, measure) pair, generates:
            AGG(expr) FILTER (WHERE col0 = val0 AND col1 = val1) AS "alias"

        Column order matches _build_wide_columns so DuckDB result positions
        align with the TableColumn metadata.

        Computed measures (divide, subtract, etc.) that reference prior measure
        keys are resolved per-combo by substituting the FILTER-wrapped column
        aliases into the expression template.

        If windows exist, wraps the base query in a CTE and adds LAG-based
        calculations in the outer SELECT.
        """
        n_rows = len(row_exprs)
        has_grouping_sets = "GROUPING SETS" in group_clause
        if has_grouping_sets:
            select_parts = [
                f"CASE WHEN GROUPING({expr}) = 1 THEN 'Total' ELSE CAST({expr} AS VARCHAR) END AS row_key_{i}"
                for i, expr in enumerate(row_exprs)
            ]
        else:
            select_parts = [f"CAST({expr} AS VARCHAR) AS row_key_{i}" for i, expr in enumerate(row_exprs)]

        # Separate base aggregation measures from computed measures.
        base_keys = {m.key for m, _ in measure_exprs if not isinstance(m.field, dict)}

        # Maps measure_key → {combo_str: col_alias} for computed measure resolution
        alias_map: dict[str, dict[str, str]] = {}

        # Pre-compute FILTER WHERE clauses per combo
        filter_cache: dict[str, str] = {}
        for combo in combos:
            cs = self._combo_to_key(combo)
            filter_cache[cs] = self._filter_clause(col_exprs, combo)

        # Generate SELECT columns in layout-correct order
        for (m, expr), combo_str, combo in self._measure_combo_pairs(measure_exprs, combos, layout):
            col_alias = _col_name(combo_str, m.key, layout)
            filter_where = filter_cache[combo_str]

            if m.key in base_keys:
                # Base aggregation — wrap directly in FILTER
                select_parts.append(
                    f'{expr} FILTER (WHERE {filter_where}) AS "{col_alias}"'
                )
            elif isinstance(m.field, dict) and not is_window_fn(m.field):
                # Computed measure — substitute prior aliases per-combo
                resolved = expr
                for prior_key in alias_map:
                    if combo_str in alias_map[prior_key]:
                        for pm, pexpr in measure_exprs:
                            if pm.key == prior_key:
                                resolved = resolved.replace(pexpr, f'"{alias_map[prior_key][combo_str]}"')
                                break
                select_parts.append(f'{resolved} AS "{col_alias}"')
            else:
                # Window-function measure — skip for base query, handled in CTE
                continue

            alias_map.setdefault(m.key, {})[combo_str] = col_alias

        order = sort_clause

        base_sql = f"""
            SELECT {', '.join(select_parts)}
            FROM {from_clause}
            {where_clause}
            GROUP BY {group_clause}
            {order}
        """

        # If windows exist, wrap in CTE and add LAG-based calculations
        if not windows:
            return base_sql

        window_cols = []
        order_expr = ', '.join(f'row_key_{i}' for i in range(n_rows))

        for win in windows:
            wtype = win.type if win.type in ("diff", "row_delta") else "pct_change"

            for combo in combos:
                combo_str = self._combo_to_key(combo)
                src_alias = _col_name(combo_str, win.source, layout)

                # Verify the source column was generated
                if win.source not in alias_map or combo_str not in alias_map[win.source]:
                    continue

                win_alias = _col_name(combo_str, win.key, layout)

                if wtype in ("diff", "row_delta"):
                    win_expr = (
                        f'("{src_alias}" - LAG("{src_alias}") '
                        f'OVER (ORDER BY {order_expr})) AS "{win_alias}"'
                    )
                else:  # pct_change / yoy
                    win_expr = (
                        f'ROUND(("{src_alias}" - LAG("{src_alias}") '
                        f'OVER (ORDER BY {order_expr})) '
                        f'/ NULLIF(LAG("{src_alias}") '
                        f'OVER (ORDER BY {order_expr}), 0), 4) AS "{win_alias}"'
                    )

                window_cols.append(win_expr)

        if not window_cols:
            return base_sql

        return f"""
            WITH pivot_base AS (
                {base_sql}
            )
            SELECT *, {', '.join(window_cols)}
            FROM pivot_base
        """

    def _build_wide_columns(
        self,
        req,
        row_fields: list[str],
        combos: list[tuple],
        measure_exprs: list[tuple],
        windows: list | None,
    ) -> list[TableColumn]:
        """Build TableColumn metadata from known column combinations.

        Produces the same column ordering as the SQL SELECT list so that
        DuckDB result columns align with the metadata.
        """
        layout = req.layout
        labels = self._row_labels(row_fields)
        columns = [TableColumn(key=f"row_key_{i}", label=labels[i]) for i in range(len(row_fields))]

        pivot_vals = [self._combo_to_key(c) for c in combos]

        # Separate base from window-fn measures (same split as SQL generation)
        base_measures = [
            (m, expr) for m, expr in measure_exprs
            if not is_window_fn(m.field)
        ]

        if layout == "by_column":
            # Outer: combos, Inner: measures → spanner = first combo part
            for cv in pivot_vals:
                spanner = cv.split("||")[0] if "||" in cv else cv
                for m, _ in base_measures:
                    key = _col_name(cv, m.key, layout)
                    if "||" in cv:
                        sub_parts = cv.split("||", 1)[1]
                        sub_label = f"{sub_parts} | {m.label or m.key}" if len(base_measures) > 1 else sub_parts
                    else:
                        sub_label = m.label or m.key.replace("_", " ").title()
                    columns.append(TableColumn(
                        key=key, label=sub_label, format=m.format, group=spanner,
                    ))
        elif layout == "by_dimension":
            # Single measure, flat columns — spanner from first combo part if multi-col
            primary_m = base_measures[0][0] if base_measures else measure_exprs[0][0]
            fmt = primary_m.format
            for cv in pivot_vals:
                key = _col_name(cv, primary_m.key, layout)
                if "||" in cv:
                    spanner, sub_label = cv.split("||", 1)
                    columns.append(TableColumn(key=key, label=sub_label, format=fmt, group=spanner))
                else:
                    columns.append(TableColumn(key=key, label=cv, format=fmt))
        else:
            # by_measure (default): Outer: measures, Inner: combos → spanner = measure label
            for m, _ in base_measures:
                m_label = m.label or m.key.replace("_", " ").title()
                for cv in pivot_vals:
                    key = _col_name(cv, m.key, layout)
                    display_label = cv.replace("||", " | ") if "||" in cv else cv
                    columns.append(TableColumn(
                        key=key, label=display_label, format=m.format, group=m_label,
                    ))

        # Window columns — same combo iteration order as SQL generation
        if windows:
            for win in windows:
                for cv in pivot_vals:
                    src_key = _col_name(cv, win.source, layout)
                    # Only add if source exists
                    if not any(c.key == src_key for c in columns):
                        continue
                    win_key = _col_name(cv, win.key, layout)
                    if layout == "by_column":
                        group = cv.split("||")[0] if "||" in cv else cv
                        lbl = win.label or win.key.replace("_", " ").title()
                    else:
                        group = win.label or win.key.replace("_", " ").title()
                        lbl = cv.replace("||", " | ") if "||" in cv else cv
                    columns.append(TableColumn(
                        key=win_key, label=lbl, format="%", group=group,
                    ))

        return columns

    # ------------------------------------------------------------------
    # 2D wide pivot (SQL-native)
    # ------------------------------------------------------------------

    def _query_2d_wide(self, req, row_exprs, col_exprs, measure_exprs,
                       from_clause, where_clause, sort_clause):
        """2D pivot: DuckDB builds the wide table via conditional aggregation.

        Replaces the old _query_2d() + reshape_pivot() + apply_windows_wide()
        pipeline. DuckDB returns the final wide table directly.
        """
        layout = req.layout
        n_rows = len(row_exprs)

        # Step 1: Discover distinct column combinations
        combos = self._discover_col_values(col_exprs, from_clause, where_clause)
        if not combos:
            # No data — return empty with row-key-only columns
            labels = self._row_labels(req.row_fields)
            return [], [TableColumn(key=f"row_key_{i}", label=labels[i]) for i in range(n_rows)]

        logger.info(f"Pivot: {len(combos)} column combinations discovered")

        # Step 2: Build GROUPING SETS for row dims only
        has_totals = req.totals and req.totals.rows
        group_clause = self._totals_sql_rows_only(row_exprs, has_totals)

        # Step 3: Generate wide SQL
        sql = self._generate_wide_sql(
            row_exprs, col_exprs, measure_exprs, combos, layout,
            from_clause, where_clause, group_clause, sort_clause,
            req.windows,
        )
        logger.debug(f"Pivot SQL (2D wide {layout}): {sql}")

        # Step 4: Execute
        raw_rows = self._execute(sql)
        row_list = [list(row) for row in raw_rows]

        # Step 5: Build column metadata
        columns = self._build_wide_columns(
            req, req.row_fields, combos, measure_exprs, req.windows,
        )

        return row_list, columns

    # ------------------------------------------------------------------
    # 1D pivot (unchanged)
    # ------------------------------------------------------------------

    def _query_1d(self, req, row_exprs, measure_exprs, from_clause, where_clause, sort_clause):
        """1D pivot: GROUP BY rows, measures as flat columns."""
        n_rows = len(row_exprs)
        has_totals = req.totals and req.totals.rows
        if has_totals:
            select_parts = [
                f"CASE WHEN GROUPING({expr}) = 1 THEN 'Total' ELSE CAST({expr} AS VARCHAR) END AS row_key_{i}"
                for i, expr in enumerate(row_exprs)
            ]
        else:
            select_parts = [f"CAST({expr} AS VARCHAR) AS row_key_{i}" for i, expr in enumerate(row_exprs)]
        for m, expr in measure_exprs:
            select_parts.append(f"{expr} AS {m.key}")
        group_clause = self._totals_sql(row_exprs, [], has_totals)

        order = sort_clause

        sql = f"""
            SELECT {', '.join(select_parts)}
            FROM {from_clause}
            {where_clause}
            GROUP BY {group_clause}
            {order}
        """
        logger.debug(f"Pivot SQL (1D): {sql}")
        rows = self._execute(sql)

        # Build column metadata
        labels = self._row_labels(req.row_fields)
        columns = [TableColumn(key=f"row_key_{i}", label=labels[i]) for i in range(n_rows)]
        for m, _ in measure_exprs:
            columns.append(TableColumn(
                key=m.key,
                label=m.label or m.key.replace("_", " ").title(),
                format=m.format,
            ))
        row_list = [list(row) for row in rows]

        if req.windows:
            row_list, columns = apply_windows_1d(row_list, columns, req.windows)

        return row_list, columns
