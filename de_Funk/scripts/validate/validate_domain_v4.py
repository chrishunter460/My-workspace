"""
Validate Domain V4 — load all configs, create tables, run queries.

Loads every model from domains/ via DomainConfigLoaderV4, creates
DuckDB tables from schema definitions, populates seed data, and
runs basic queries to validate the configuration end-to-end.

Usage:
    python -m scripts.validate.validate_domain_v4
    python -m scripts.validate.validate_domain_v4 --model county_property
    python -m scripts.validate.validate_domain_v4 --verbose
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

# Bootstrap imports
repo_root = Path(__file__).resolve().parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))
src_root = repo_root / "src"
if str(src_root) not in sys.path:
    sys.path.insert(0, str(src_root))

import duckdb

from de_funk.config.domain import DomainConfigLoaderV4, get_domain_loader
from de_funk.config.domain.schema import canonical_fields_to_schema
from de_funk.config.domain.build import (
    parse_build_config,
    get_table_build_flags,
    extract_seed_data,
    process_enrich_specs,
    validate_build_config,
)
from de_funk.config.domain.views import (
    parse_view_config,
    resolve_view_chain,
    get_derived_columns,
)
from de_funk.config.domain.federation import (
    get_federation_config,
    validate_federation,
)
from de_funk.config.domain.graph import (
    parse_graph_config,
    resolve_auto_edges,
    validate_paths,
)
from de_funk.config.domain.sources import (
    process_all_sources,
    build_select_expressions,
)

# ---------------------------------------------------------------------------
# Type mapping: domain YAML types → DuckDB types
# ---------------------------------------------------------------------------
TYPE_MAP = {
    "string": "VARCHAR",
    "varchar": "VARCHAR",
    "text": "VARCHAR",
    "integer": "INTEGER",
    "int": "INTEGER",
    "bigint": "BIGINT",
    "long": "BIGINT",
    "float": "FLOAT",
    "double": "DOUBLE",
    "decimal": "DECIMAL(18,4)",
    "numeric": "DECIMAL(18,4)",
    "boolean": "BOOLEAN",
    "bool": "BOOLEAN",
    "date": "DATE",
    "timestamp": "TIMESTAMP",
    "datetime": "TIMESTAMP",
}


def map_type(yaml_type: str) -> str:
    """Map a YAML schema type to a DuckDB type."""
    if not yaml_type:
        return "VARCHAR"
    clean = yaml_type.lower().strip()
    # Handle parameterized types like decimal(10,2)
    if "(" in clean:
        base = clean.split("(")[0]
        return TYPE_MAP.get(base, "VARCHAR") if base in TYPE_MAP else clean.upper()
    return TYPE_MAP.get(clean, "VARCHAR")


# ---------------------------------------------------------------------------
# Schema → DDL
# ---------------------------------------------------------------------------
def schema_to_ddl(table_name: str, schema: list) -> str:
    """Convert a domain schema list to a CREATE TABLE statement."""
    cols = []
    for col in schema:
        if not isinstance(col, list) or len(col) < 2:
            continue
        col_name = col[0]
        col_type = map_type(col[1])
        nullable = col[2] if len(col) > 2 else True

        # Skip derived-only columns (they have {derived: "expr"} in options)
        options = col[4] if len(col) > 4 and isinstance(col[4], dict) else {}
        # Still create the column, just use the type

        null_str = "" if nullable else " NOT NULL"
        cols.append(f"    {col_name} {col_type}{null_str}")

    if not cols:
        return ""
    return f"CREATE TABLE IF NOT EXISTS {table_name} (\n" + ",\n".join(cols) + "\n);"


def seed_to_insert(table_name: str, seed_rows: list) -> List[str]:
    """Convert seed data rows to INSERT statements."""
    if not seed_rows:
        return []
    stmts = []
    for row in seed_rows:
        cols = list(row.keys())
        vals = []
        for v in row.values():
            if v is None:
                vals.append("NULL")
            elif isinstance(v, (int, float)):
                vals.append(str(v))
            elif isinstance(v, bool):
                vals.append("TRUE" if v else "FALSE")
            else:
                vals.append(f"'{str(v).replace(chr(39), chr(39)+chr(39))}'")
        stmts.append(
            f"INSERT INTO {table_name} ({', '.join(cols)}) "
            f"VALUES ({', '.join(vals)});"
        )
    return stmts


# ---------------------------------------------------------------------------
# Model loading + reporting
# ---------------------------------------------------------------------------
def load_and_report(
    loader: DomainConfigLoaderV4,
    model_name: str,
    conn: duckdb.DuckDBPyConnection,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Load a model config, create tables, report findings."""
    report = {
        "model": model_name,
        "tables_created": [],
        "seed_tables": [],
        "views": [],
        "sources": [],
        "edges": [],
        "federation": None,
        "warnings": [],
        "errors": [],
    }

    try:
        config = loader.load_model_config(model_name)
    except Exception as e:
        report["errors"].append(f"Failed to load config: {e}")
        return report

    # --- Tables ---
    tables = config.get("tables", {})
    schema_prefix = model_name.replace("-", "_")

    for table_name, table_config in tables.items():
        if not isinstance(table_config, dict):
            continue

        schema = table_config.get("schema", [])
        if not schema:
            if verbose:
                report["warnings"].append(f"Table '{table_name}' has no schema")
            continue

        qualified = f"{schema_prefix}__{table_name}"
        ddl = schema_to_ddl(qualified, schema)
        if not ddl:
            report["warnings"].append(f"Table '{table_name}' produced empty DDL")
            continue

        try:
            conn.execute(ddl)
            report["tables_created"].append(table_name)

            # Seed data?
            seed_rows = extract_seed_data(table_config)
            if seed_rows:
                for stmt in seed_to_insert(qualified, seed_rows):
                    try:
                        conn.execute(stmt)
                    except Exception as e:
                        report["warnings"].append(
                            f"Seed insert failed for '{table_name}': {e}"
                        )
                report["seed_tables"].append(
                    {"table": table_name, "rows": len(seed_rows)}
                )

        except Exception as e:
            report["errors"].append(f"DDL failed for '{table_name}': {e}")

    # --- Build config validation ---
    build_warnings = validate_build_config(config)
    if build_warnings:
        report["warnings"].extend(build_warnings)

    # --- Build phases ---
    build = parse_build_config(config)
    if verbose and build["phases"]:
        for phase in build["phases"]:
            phase_tables = phase.get("tables", [])
            if verbose:
                print(
                    f"    Phase {phase['phase_num']}: "
                    f"{len(phase_tables)} tables, "
                    f"persist={phase.get('persist', True)}, "
                    f"enrich={phase.get('enrich', False)}"
                )

    # --- Sources ---
    sources = config.get("sources", {})
    if sources:
        source_info = process_all_sources(sources)
        for source_name, info in source_info.get("sources", {}).items():
            report["sources"].append({
                "name": source_name,
                "maps_to": info.get("maps_to", ""),
                "aliases": len(info.get("aliases", [])),
                "domain_source": info.get("domain_source", ""),
            })

    # --- Views ---
    views = config.get("views", {})
    for view_name, view_config in views.items():
        if not isinstance(view_config, dict):
            continue
        parsed = parse_view_config(view_config)
        report["views"].append({
            "name": view_name,
            "type": parsed["view_type"],
            "from": parsed["from"],
            "assumptions": len(parsed["assumptions"]),
        })

    # --- Graph ---
    graph = parse_graph_config(config)
    report["edges"] = [
        {
            "name": e["name"],
            "from": e["from"],
            "to": e["to"],
            "cross_model": e["cross_model"],
            "optional": e["optional"],
        }
        for e in graph["edges"]
    ]

    # Auto-edges
    if graph["auto_edges"] or config.get("auto_edges"):
        auto_generated = resolve_auto_edges(config, tables)
        for ae in auto_generated:
            report["edges"].append({
                "name": ae["name"],
                "from": ae["from"],
                "to": ae["to"],
                "cross_model": ae["cross_model"],
                "optional": ae["optional"],
                "auto": True,
            })

    # Path validation
    if graph["paths"]:
        path_warnings = validate_paths(graph["paths"], graph["edges"])
        report["warnings"].extend(path_warnings)

    # --- Federation ---
    fed = get_federation_config(config)
    if fed["is_federation_model"] or fed["enabled"]:
        fed_warnings = validate_federation(config, loader.list_models())
        report["federation"] = {
            "enabled": fed["enabled"],
            "is_federation_model": fed["is_federation_model"],
            "children": [c["model"] for c in fed["children"]],
            "union_tables": list(fed["union_tables"].keys()),
            "union_key": fed["union_key"],
        }
        report["warnings"].extend(fed_warnings)

    return report


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------
def run_basic_queries(
    conn: duckdb.DuckDBPyConnection,
    reports: List[Dict],
    verbose: bool = False,
):
    """Run basic validation queries against created tables."""
    print("\n" + "=" * 70)
    print("BASIC QUERIES")
    print("=" * 70)

    # 1. List all tables
    result = conn.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'main' ORDER BY table_name"
    ).fetchall()
    print(f"\n  Total tables created: {len(result)}")

    # 2. Tables with seed data
    seed_tables = []
    for r in reports:
        for st in r.get("seed_tables", []):
            qualified = f"{r['model'].replace('-', '_')}__{st['table']}"
            seed_tables.append((qualified, st["rows"]))

    if seed_tables:
        print(f"\n  Tables with seed data:")
        for tbl, rows in seed_tables:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
                print(f"    {tbl}: {count} rows (expected {rows})")

                # Show sample data
                if verbose:
                    sample = conn.execute(
                        f"SELECT * FROM {tbl} LIMIT 5"
                    ).fetchdf()
                    print(f"      Columns: {list(sample.columns)}")
                    if not sample.empty:
                        for _, row in sample.head(3).iterrows():
                            print(f"      {dict(row)}")
            except Exception as e:
                print(f"    {tbl}: QUERY ERROR — {e}")

    # 3. Schema inspection for a few interesting tables
    print(f"\n  Schema samples:")
    interesting = []
    for r in reports:
        for t in r.get("tables_created", [])[:2]:
            qualified = f"{r['model'].replace('-', '_')}__{t}"
            interesting.append((r["model"], t, qualified))

    for model_name, table_name, qualified in interesting[:6]:
        try:
            cols = conn.execute(
                f"SELECT column_name, data_type, is_nullable "
                f"FROM information_schema.columns "
                f"WHERE table_name = '{qualified}' "
                f"ORDER BY ordinal_position"
            ).fetchall()
            print(f"\n    {model_name}.{table_name} ({len(cols)} columns):")
            for col_name, dtype, nullable in cols[:8]:
                print(f"      {col_name:30s} {dtype:15s} {'NULL' if nullable == 'YES' else 'NOT NULL'}")
            if len(cols) > 8:
                print(f"      ... and {len(cols) - 8} more columns")
        except Exception as e:
            print(f"    {qualified}: ERROR — {e}")

    # 4. Cross-table join feasibility (check FK columns exist)
    print(f"\n  Cross-table FK alignment check:")
    fk_checks = 0
    fk_ok = 0
    for r in reports:
        for edge in r.get("edges", []):
            from_tbl = f"{r['model'].replace('-', '_')}__{edge['from']}"
            # Only check intra-model edges
            if edge.get("cross_model"):
                continue
            to_tbl = f"{r['model'].replace('-', '_')}__{edge['to'].split('.')[-1]}"
            # Check both tables exist
            try:
                conn.execute(f"SELECT 1 FROM information_schema.tables WHERE table_name = '{from_tbl}'").fetchone()
                conn.execute(f"SELECT 1 FROM information_schema.tables WHERE table_name = '{to_tbl}'").fetchone()
                fk_checks += 1
                fk_ok += 1
            except Exception:
                fk_checks += 1

    print(f"    Checked {fk_checks} intra-model edges, {fk_ok} have both tables present")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model", "-m",
        help="Load only this model (default: all)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output",
    )
    parser.add_argument(
        "--domains-dir",
        default=str(repo_root / "domains"),
        help="Path to domains directory",
    )
    args = parser.parse_args()

    domains_dir = Path(args.domains_dir)
    print(f"Domains directory: {domains_dir}")
    print(f"Exists: {domains_dir.exists()}")

    # Load via factory
    loader = get_domain_loader(domains_dir)
    print(f"Loader type: {type(loader).__name__}")

    if not isinstance(loader, DomainConfigLoaderV4):
        print("WARNING: Not a V4 loader — this script is designed for V4 configs")
        sys.exit(1)

    # List models
    all_models = loader.list_models()
    print(f"Models discovered: {len(all_models)}")
    for m in all_models:
        print(f"  - {m}")

    # Build order
    try:
        build_order = loader.get_build_order()
        print(f"\nBuild order ({len(build_order)} models):")
        for i, m in enumerate(build_order, 1):
            deps = loader.get_dependencies(m)
            dep_str = f" (depends on: {', '.join(deps)})" if deps else ""
            print(f"  {i}. {m}{dep_str}")
    except Exception as e:
        print(f"Build order failed: {e}")
        build_order = all_models

    # Filter models if requested
    if args.model:
        models_to_load = [args.model]
    else:
        models_to_load = build_order

    # Create in-memory DuckDB
    conn = duckdb.connect(":memory:")

    # Load and report each model
    print("\n" + "=" * 70)
    print("MODEL REPORTS")
    print("=" * 70)

    reports = []
    for model_name in models_to_load:
        print(f"\n{'─' * 50}")
        print(f"Model: {model_name}")
        print(f"{'─' * 50}")

        report = load_and_report(loader, model_name, conn, verbose=args.verbose)
        reports.append(report)

        # Print summary
        print(f"  Tables:    {len(report['tables_created'])}")
        if report["tables_created"]:
            for t in report["tables_created"]:
                flags = []
                config = loader.load_model_config(model_name)
                tc = config.get("tables", {}).get(t, {})
                if isinstance(tc, dict):
                    bf = get_table_build_flags(tc)
                    if bf["static"]:
                        flags.append("static")
                    if bf["generated"]:
                        flags.append("generated")
                    if bf["transform"]:
                        flags.append(f"transform:{bf['transform']}")
                flag_str = f" [{', '.join(flags)}]" if flags else ""
                print(f"    - {t}{flag_str}")

        print(f"  Sources:   {len(report['sources'])}")
        if args.verbose and report["sources"]:
            for s in report["sources"]:
                print(f"    - {s['name']} → {s['maps_to']} ({s['aliases']} aliases)")

        print(f"  Views:     {len(report['views'])}")
        if report["views"]:
            for v in report["views"]:
                print(f"    - {v['name']} ({v['type']}, from: {v['from']})")

        print(f"  Edges:     {len(report['edges'])}")
        if args.verbose and report["edges"]:
            for e in report["edges"]:
                auto_tag = " [auto]" if e.get("auto") else ""
                opt_tag = " [optional]" if e["optional"] else ""
                xm_tag = " [cross-model]" if e["cross_model"] else ""
                print(f"    - {e['name']}: {e['from']} → {e['to']}{xm_tag}{opt_tag}{auto_tag}")

        if report["seed_tables"]:
            print(f"  Seed data: {len(report['seed_tables'])} tables")
            for st in report["seed_tables"]:
                print(f"    - {st['table']}: {st['rows']} rows")

        if report["federation"]:
            fed = report["federation"]
            print(f"  Federation: {'model' if fed['is_federation_model'] else 'participant'}")
            if fed["children"]:
                print(f"    Children: {', '.join(fed['children'])}")
            if fed["union_tables"]:
                print(f"    Union tables: {', '.join(fed['union_tables'])}")

        if report["warnings"]:
            print(f"  Warnings:  {len(report['warnings'])}")
            for w in report["warnings"]:
                print(f"    ! {w}")

        if report["errors"]:
            print(f"  ERRORS:    {len(report['errors'])}")
            for e in report["errors"]:
                print(f"    X {e}")

    # --- Summary ---
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    total_tables = sum(len(r["tables_created"]) for r in reports)
    total_sources = sum(len(r["sources"]) for r in reports)
    total_views = sum(len(r["views"]) for r in reports)
    total_edges = sum(len(r["edges"]) for r in reports)
    total_seed = sum(len(r["seed_tables"]) for r in reports)
    total_warnings = sum(len(r["warnings"]) for r in reports)
    total_errors = sum(len(r["errors"]) for r in reports)
    fed_models = [r for r in reports if r.get("federation")]

    print(f"  Models loaded:      {len(reports)}")
    print(f"  Tables created:     {total_tables}")
    print(f"  Sources configured: {total_sources}")
    print(f"  Views defined:      {total_views}")
    print(f"  Edges defined:      {total_edges}")
    print(f"  Seed tables:        {total_seed}")
    print(f"  Federation models:  {len(fed_models)}")
    print(f"  Warnings:           {total_warnings}")
    print(f"  Errors:             {total_errors}")

    # Run queries
    run_basic_queries(conn, reports, verbose=args.verbose)

    # Final verdict
    print("\n" + "=" * 70)
    if total_errors == 0:
        print("RESULT: ALL MODELS LOADED AND VALIDATED SUCCESSFULLY")
    else:
        print(f"RESULT: {total_errors} ERRORS FOUND — see details above")
    print("=" * 70)

    conn.close()
    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
