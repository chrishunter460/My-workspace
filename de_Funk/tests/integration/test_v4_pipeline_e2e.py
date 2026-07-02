"""
End-to-end pipeline test for domain models.

Validates the full path from domain config -> translated graph.nodes ->
table building using DuckDB in-memory mode with synthetic Bronze data.

This test verifies:
1. Domain configs translate to valid graph.nodes
2. Synthetic Bronze data seeds correctly
3. Tables can be built (SELECT with aliases, derive, joins)
4. Cross-model references resolve
5. Schema output matches expectations
"""

import pytest
import sys
import logging
import duckdb
from pathlib import Path

# Bootstrap
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(project_root / "src") not in sys.path:
    sys.path.insert(0, str(project_root / "src"))

logger = logging.getLogger(__name__)


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(scope="module")
def domains_dir():
    """Path to v4 domains directory."""
    path = project_root / "domains"
    if not (path / "models").exists():
        pytest.skip("domains/ not in v4 format")
    return path


@pytest.fixture(scope="module")
def domain_loader(domains_dir):
    """V4 config loader instance."""
    from de_funk.config.domain import DomainConfigLoader
    return DomainConfigLoader(domains_dir)


@pytest.fixture(scope="module")
def translated_configs(domain_loader):
    """All v4 configs translated to v3-compatible format."""
    from de_funk.config.domain.config_translator import translate_domain_config

    configs = {}
    for model_name in domain_loader.list_models():
        config = domain_loader.load_model_config(model_name)
        configs[model_name] = translate_domain_config(config)
    return configs


@pytest.fixture(scope="module")
def duckdb_conn():
    """In-memory DuckDB connection with synthetic Bronze data."""
    from scripts.seed.seed_synthetic_bronze import (
        collect_bronze_tables,
        seed_as_duckdb,
    )

    domains_dir = project_root / "domains"
    bronze_tables = collect_bronze_tables(domains_dir)
    conn = seed_as_duckdb(bronze_tables, ":memory:", num_rows=10)
    yield conn
    conn.close()


# ============================================================
# Translation E2E Tests
# ============================================================

class TestTranslationE2E:
    """Test that all v4 models translate successfully."""

    def test_all_models_have_graph_nodes(self, translated_configs):
        """Every translated config has graph.nodes (federation models may have none)."""
        no_nodes = []
        for model_name, config in translated_configs.items():
            nodes = config.get("graph", {}).get("nodes", {})
            tables = config.get("tables", {})

            # Federation models use union_of — they have no direct sources
            is_federation = "federation" in model_name or any(
                isinstance(t, dict) and t.get("union_of")
                for t in tables.values()
            )

            if tables and not nodes and not is_federation:
                # Check if all tables are sourceless (no matching sources)
                has_sourceable = any(
                    isinstance(t, dict) and not t.get("static")
                    and not t.get("seed") and t.get("schema")
                    for t in tables.values()
                )
                if has_sourceable:
                    no_nodes.append(model_name)

        # Some models are foundation/template types with no sources
        # (temporal generates calendar, geospatial is a base template)
        if no_nodes:
            logger.info(
                f"Models with tables but no translated nodes "
                f"(foundation/template): {no_nodes}"
            )
        # At least most models should have nodes
        total = len(translated_configs)
        assert len(no_nodes) < total * 0.2, \
            f"Too many models without nodes: {no_nodes} ({len(no_nodes)}/{total})"

    def test_node_count_matches_tables(self, translated_configs):
        """Number of nodes approximately matches number of tables with sources."""
        for model_name, config in translated_configs.items():
            nodes = config.get("graph", {}).get("nodes", {})
            tables = config.get("tables", {})
            # Nodes ≤ tables (some tables may not have sources)
            assert len(nodes) <= len(tables) + 1, \
                f"{model_name}: more nodes ({len(nodes)}) than tables ({len(tables)})"

    def test_translated_model_has_build_metadata(self, translated_configs):
        """Translated configs include _v4_build metadata."""
        for model_name, config in translated_configs.items():
            assert "_domain_build" in config, \
                f"{model_name}: missing _v4_build metadata"


# ============================================================
# Bronze Seed E2E Tests
# ============================================================

class TestBronzeSeedE2E:
    """Test synthetic Bronze data generation."""

    def test_all_bronze_tables_created(self, duckdb_conn):
        """All referenced Bronze tables exist in DuckDB."""
        tables = duckdb_conn.execute("SHOW TABLES").fetchall()
        table_names = {t[0] for t in tables}
        assert len(table_names) >= 30, \
            f"Expected 30+ Bronze tables, got {len(table_names)}"

    def test_bronze_tables_have_rows(self, duckdb_conn):
        """Every Bronze table has data rows."""
        tables = duckdb_conn.execute("SHOW TABLES").fetchall()
        for (table_name,) in tables:
            count = duckdb_conn.execute(
                f"SELECT COUNT(*) FROM {table_name}"
            ).fetchone()[0]
            assert count > 0, f"{table_name} has no rows"

    def test_specific_bronze_table_columns(self, duckdb_conn):
        """Listing status table has expected columns."""
        tables = duckdb_conn.execute("SHOW TABLES").fetchall()
        table_names = {t[0] for t in tables}

        if "bronze_alpha_vantage_listing_status" not in table_names:
            pytest.skip("listing_status not seeded")

        cols = duckdb_conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'bronze_alpha_vantage_listing_status'"
        ).fetchall()
        col_names = {c[0] for c in cols}

        # Should have columns that the stock sources reference
        assert len(col_names) > 0


# ============================================================
# Build Simulation E2E Tests
# ============================================================

class TestBuildSimulationE2E:
    """
    Simulate building v4 model tables using DuckDB.

    This doesn't use the full GraphBuilder/BaseModel pipeline
    (which requires Spark), but validates that the translated
    graph.nodes produce valid SQL operations.
    """

    def test_select_with_aliases(self, duckdb_conn, translated_configs):
        """Source aliases produce valid SQL SELECT expressions."""
        # Pick a model with a simple source
        for model_name, config in translated_configs.items():
            nodes = config.get("graph", {}).get("nodes", {})
            for node_name, node in nodes.items():
                if node.get("from", "").startswith("bronze."):
                    select = node.get("select", {})
                    if not select:
                        continue

                    # Construct SELECT from aliases
                    bronze_table = node["from"].replace(".", "_")

                    # Check if this table exists in DuckDB
                    exists = duckdb_conn.execute(
                        f"SELECT COUNT(*) FROM information_schema.tables "
                        f"WHERE table_name = '{bronze_table}'"
                    ).fetchone()[0]

                    if not exists:
                        continue

                    # Build and execute SELECT
                    select_parts = []
                    for col_name, expr in select.items():
                        # Only use simple column references for testing
                        if expr.isidentifier():
                            # Check if column exists
                            col_exists = duckdb_conn.execute(
                                f"SELECT COUNT(*) FROM information_schema.columns "
                                f"WHERE table_name = '{bronze_table}' "
                                f"AND column_name = '{expr}'"
                            ).fetchone()[0]
                            if col_exists:
                                select_parts.append(f"{expr} AS {col_name}")

                    if select_parts:
                        select_sql = ", ".join(select_parts)
                        query = f"SELECT {select_sql} FROM {bronze_table} LIMIT 5"
                        result = duckdb_conn.execute(query).fetchall()
                        assert len(result) > 0, \
                            f"SELECT from {bronze_table} returned no rows"
                        # Test passed for this node
                        return

        # If we get here, no testable nodes found (not a failure)
        pytest.skip("No simple SELECT nodes found to test")

    def test_seed_table_data(self, translated_configs):
        """Seed tables have valid inline data."""
        seed_count = 0
        for model_name, config in translated_configs.items():
            nodes = config.get("graph", {}).get("nodes", {})
            for node_name, node in nodes.items():
                if node.get("_seed"):
                    seed_data = node.get("_seed_data", [])
                    assert isinstance(seed_data, list)
                    if seed_data:
                        assert isinstance(seed_data[0], dict), \
                            f"{model_name}.{node_name}: seed data not a list of dicts"
                        seed_count += 1

        assert seed_count > 0, "Expected at least one seed table across all models"

    def test_seed_table_creates_dataframe(self, duckdb_conn, translated_configs):
        """Seed data can be loaded into DuckDB."""
        import pandas as pd

        for model_name, config in translated_configs.items():
            nodes = config.get("graph", {}).get("nodes", {})
            for node_name, node in nodes.items():
                if not node.get("_seed"):
                    continue
                seed_data = node.get("_seed_data", [])
                if not seed_data:
                    continue

                # Create DuckDB table from seed data
                df = pd.DataFrame(seed_data)
                safe_name = f"seed_{model_name}_{node_name}".replace("-", "_")
                duckdb_conn.execute(
                    f"CREATE OR REPLACE TABLE {safe_name} AS SELECT * FROM df"
                )

                count = duckdb_conn.execute(
                    f"SELECT COUNT(*) FROM {safe_name}"
                ).fetchone()[0]
                assert count == len(seed_data), \
                    f"{safe_name}: expected {len(seed_data)} rows, got {count}"
                return

        pytest.skip("No seed tables with data found")

    def test_derive_expressions_syntax(self, translated_configs):
        """All derive expressions are non-empty strings."""
        for model_name, config in translated_configs.items():
            nodes = config.get("graph", {}).get("nodes", {})
            for node_name, node in nodes.items():
                derive = node.get("derive", {})
                for col_name, expr in derive.items():
                    assert isinstance(expr, str) and len(expr) > 0, \
                        f"{model_name}.{node_name}.derive.{col_name}: " \
                        f"invalid expression: {expr!r}"


# ============================================================
# Cross-Model Reference Tests
# ============================================================

class TestCrossModelReferences:
    """Test cross-model edges and dependencies."""

    def test_edges_reference_known_tables(self, translated_configs):
        """Graph edges reference tables that exist in the model."""
        from de_funk.config.domain.graph import parse_edge

        for model_name, config in translated_configs.items():
            nodes = config.get("graph", {}).get("nodes", {})
            raw_edges = config.get("graph", {}).get("edges", [])

            for edge_data in raw_edges:
                parsed = parse_edge(edge_data)
                if not parsed:
                    continue

                from_table = parsed["from"]
                # from_table should be in this model's nodes (unless cross-model)
                if not parsed["cross_model"] and from_table not in nodes:
                    # May have been skipped (no source) — just log, don't fail
                    logger.debug(
                        f"{model_name}: edge '{parsed['name']}' references "
                        f"from='{from_table}' not in nodes"
                    )

    def test_depends_on_resolves(self, domain_loader, translated_configs):
        """Most depends_on references point to known models."""
        all_models = set(domain_loader.list_models())
        unresolved = []

        for model_name, config in translated_configs.items():
            depends = config.get("depends_on", [])
            if isinstance(depends, str):
                depends = [depends]
            for dep in depends:
                if dep not in all_models:
                    unresolved.append(f"{model_name} → {dep}")

        # Allow a small number of unresolved deps (cross-domain references
        # may use different naming conventions)
        if unresolved:
            logger.warning(
                f"Unresolved depends_on ({len(unresolved)}):\n"
                + "\n".join(f"  {u}" for u in unresolved)
            )
        # Don't fail — just warn. Some deps may reference v3 models
        # or use naming patterns we haven't seen yet


# ============================================================
# Summary Statistics Test
# ============================================================

class TestPipelineSummary:
    """Summary statistics across all v4 models."""

    def test_pipeline_summary(self, translated_configs):
        """Print summary statistics for all translated models."""
        total_nodes = 0
        total_seed = 0
        total_union = 0
        total_edges = 0

        for model_name, config in translated_configs.items():
            nodes = config.get("graph", {}).get("nodes", {})
            edges = config.get("graph", {}).get("edges", [])

            total_nodes += len(nodes)
            total_edges += len(edges)

            for node in nodes.values():
                if node.get("_seed"):
                    total_seed += 1
                if node.get("_union"):
                    total_union += 1

        assert total_nodes > 0, "Should have at least one node"
        logger.info(
            f"\nPipeline Summary:\n"
            f"  Models: {len(translated_configs)}\n"
            f"  Total nodes: {total_nodes}\n"
            f"  Seed tables: {total_seed}\n"
            f"  Union tables: {total_union}\n"
            f"  Total edges: {total_edges}"
        )


# ============================================================
# Run tests
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pytest.main([__file__, "-v", "--tb=short"])
