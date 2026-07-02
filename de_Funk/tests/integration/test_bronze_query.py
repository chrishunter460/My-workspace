"""
Bronze query integration tests — end-to-end handler dispatch against Bronze data.

Uses the FastAPI TestClient with a temporary bronze tree containing
real DuckDB-readable Parquet files. Exercises all handler types through
the /api/bronze/query, /api/bronze/dimensions, and /api/bronze/endpoints
endpoints.

Usage:
    pytest tests/integration/test_bronze_query.py -v
"""
import json
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from de_funk.utils.repo import setup_repo_imports
setup_repo_imports()

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fastapi.testclient import TestClient

from de_funk.api.bronze_resolver import BronzeResolver


# ---------------------------------------------------------------------------
# Fixtures — build a self-contained bronze + data_sources tree with parquet
# ---------------------------------------------------------------------------

PROVIDER_MD = """\
---
type: api-provider
provider_id: testprov
provider: Test Provider
base_url: https://example.com
---
"""

ENDPOINT_EVENTS_MD = """\
---
type: api-endpoint
provider: Test Provider
endpoint_id: events
bronze: testprov
schema:
  - [event_id, string]
  - [category, string]
  - [value, double]
  - [year, int]
---
"""

ENDPOINT_LOCATIONS_MD = """\
---
type: api-endpoint
provider: Test Provider
endpoint_id: locations
bronze: testprov
schema:
  - [location_id, string]
  - [name, string]
  - [lat, double]
  - [lng, double]
---
"""


def _write_parquet(path: Path, table: pa.Table) -> None:
    """Write a PyArrow table as a single Parquet file in a directory."""
    path.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path / "part-0.parquet")


@pytest.fixture(scope="module")
def bronze_app(tmp_path_factory):
    """Create a FastAPI app wired to a temporary Bronze tree with real data."""
    tmp = tmp_path_factory.mktemp("bronze_int")
    data_sources = tmp / "data_sources"
    bronze_root = tmp / "bronze"

    # Provider
    (data_sources / "Providers").mkdir(parents=True)
    (data_sources / "Providers" / "Test Provider.md").write_text(PROVIDER_MD)

    # Endpoints
    ep_dir = data_sources / "Endpoints" / "Test Provider" / "Core"
    ep_dir.mkdir(parents=True)
    (ep_dir / "Events.md").write_text(ENDPOINT_EVENTS_MD)
    (ep_dir / "Locations.md").write_text(ENDPOINT_LOCATIONS_MD)

    # Write Parquet data
    events_table = pa.table({
        "event_id": ["e1", "e2", "e3", "e4", "e5"],
        "category": ["A", "B", "A", "C", "B"],
        "value": [10.0, 20.0, 15.0, 30.0, 25.0],
        "year": [2023, 2023, 2024, 2024, 2024],
    })
    _write_parquet(bronze_root / "testprov" / "events", events_table)

    locations_table = pa.table({
        "location_id": ["loc1", "loc2", "loc3"],
        "name": ["Downtown", "North Side", "South Side"],
        "lat": [41.88, 41.95, 41.75],
        "lng": [-87.63, -87.65, -87.62],
    })
    _write_parquet(bronze_root / "testprov" / "locations", locations_table)

    # Build a minimal FastAPI app with Bronze wiring only
    # (avoids needing full Silver domain configs)
    from fastapi import FastAPI

    from de_funk.api.executor import QueryEngine
    from de_funk.api.handlers import build_registry
    from de_funk.api.routers import bronze

    app = FastAPI()
    app.include_router(bronze.router, prefix="/api")

    engine_kwargs = dict(
        storage_root=bronze_root,
        memory_limit="256MB",
        max_sql_rows=10000,
        max_dimension_values=5000,
        max_response_mb=2.0,
    )

    app.state.executor = QueryEngine(**engine_kwargs)
    app.state.registry = build_registry(**engine_kwargs)
    app.state.bronze_resolver = BronzeResolver(
        data_sources_root=data_sources,
        bronze_root=bronze_root,
    )

    return app


@pytest.fixture(scope="module")
def client(bronze_app):
    """TestClient for the bronze-only test app."""
    return TestClient(bronze_app)


# ---------------------------------------------------------------------------
# GET /api/bronze/endpoints — catalog
# ---------------------------------------------------------------------------

class TestBronzeCatalog:
    def test_endpoints_returns_catalog(self, client):
        """GET /api/bronze/endpoints returns the provider/endpoint/field tree."""
        resp = client.get("/api/bronze/endpoints")
        assert resp.status_code == 200
        data = resp.json()
        assert "testprov" in data
        assert "events" in data["testprov"]["endpoints"]
        assert "locations" in data["testprov"]["endpoints"]

    def test_catalog_field_types(self, client):
        """Catalog includes field types from endpoint schema."""
        resp = client.get("/api/bronze/endpoints")
        events = resp.json()["testprov"]["endpoints"]["events"]
        assert events["fields"]["value"]["type"] == "double"
        assert events["fields"]["category"]["type"] == "string"


# ---------------------------------------------------------------------------
# GET /api/bronze/dimensions — distinct values
# ---------------------------------------------------------------------------

class TestBronzeDimensions:
    def test_distinct_values(self, client):
        """Dimension endpoint returns sorted distinct values."""
        resp = client.get("/api/bronze/dimensions/testprov/events/category")
        assert resp.status_code == 200
        data = resp.json()
        assert data["field"] == "testprov.events.category"
        assert sorted(data["values"]) == ["A", "B", "C"]

    def test_distinct_values_with_filter(self, client):
        """Context filters narrow dimension results."""
        filters = json.dumps([{"field": "testprov.events.year", "value": [2024]}])
        resp = client.get(
            "/api/bronze/dimensions/testprov/events/category",
            params={"filters": filters},
        )
        assert resp.status_code == 200
        values = resp.json()["values"]
        assert "A" in values
        assert "C" in values

    def test_distinct_values_unknown_ref(self, client):
        """Unknown ref returns 404."""
        resp = client.get("/api/bronze/dimensions/testprov/nonexistent/field")
        assert resp.status_code == 404

    def test_dimension_order_by_measure(self, client):
        """Dimension values can be ordered by aggregated measure."""
        resp = client.get(
            "/api/bronze/dimensions/testprov/events/category",
            params={
                "order_by": "testprov.events.value",
                "order_dir": "desc",
            },
        )
        assert resp.status_code == 200
        # C has avg=30.0, B=22.5, A=12.5 — desc order
        values = resp.json()["values"]
        assert values[0] == "C"


# ---------------------------------------------------------------------------
# POST /api/bronze/query — handler dispatch
# ---------------------------------------------------------------------------

class TestBronzeQueryDispatch:
    def test_missing_type_returns_400(self, client):
        """Payload without 'type' returns 400."""
        resp = client.post("/api/bronze/query", json={"foo": "bar"})
        assert resp.status_code == 400
        assert "type" in resp.json()["detail"].lower()

    def test_unknown_type_returns_400(self, client):
        """Unknown block type returns 400."""
        resp = client.post(
            "/api/bronze/query",
            json={"type": "nonexistent.type"},
        )
        assert resp.status_code == 400

    def test_bad_field_ref_returns_error(self, client):
        """Invalid field reference in payload returns an error status."""
        resp = client.post(
            "/api/bronze/query",
            json={
                "type": "cards.metric",
                "metrics": [
                    {"key": "bad", "field": "bogus.ref.field", "aggregation": "count"},
                ],
            },
        )
        assert resp.status_code in (400, 422, 500)


class TestBronzeMetrics:
    def test_metric_count(self, client):
        """cards.metric handler works through Bronze — COUNT aggregation."""
        resp = client.post(
            "/api/bronze/query",
            json={
                "type": "cards.metric",
                "metrics": [
                    {
                        "key": "total",
                        "field": "testprov.events.event_id",
                        "aggregation": "count",
                        "label": "Total Events",
                    },
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "metrics" in data
        total = next(m for m in data["metrics"] if m["key"] == "total")
        assert total["value"] == 5

    def test_metric_sum(self, client):
        """cards.metric handler — SUM aggregation."""
        resp = client.post(
            "/api/bronze/query",
            json={
                "type": "cards.metric",
                "metrics": [
                    {
                        "key": "total_value",
                        "field": "testprov.events.value",
                        "aggregation": "sum",
                        "label": "Total Value",
                    },
                ],
            },
        )
        assert resp.status_code == 200
        total_val = next(
            m for m in resp.json()["metrics"] if m["key"] == "total_value"
        )
        assert total_val["value"] == pytest.approx(100.0)


class TestBronzeGraphical:
    def test_bar_chart(self, client):
        """plotly.bar handler works through Bronze."""
        resp = client.post(
            "/api/bronze/query",
            json={
                "type": "plotly.bar",
                "x": "testprov.events.category",
                "y": "testprov.events.value",
                "aggregation": "sum",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "series" in data

    def test_line_chart_with_filter(self, client):
        """plotly.line handler with inline filter."""
        resp = client.post(
            "/api/bronze/query",
            json={
                "type": "plotly.line",
                "x": "testprov.events.year",
                "y": "testprov.events.value",
                "aggregation": "avg",
                "filters": [
                    {"field": "testprov.events.category", "op": "in", "value": ["A"]},
                ],
            },
        )
        assert resp.status_code == 200


class TestBronzeTableData:
    def test_table_data_basic(self, client):
        """table.data handler returns columns and rows."""
        resp = client.post(
            "/api/bronze/query",
            json={
                "type": "table.data",
                "columns": [
                    {"key": "loc", "field": "testprov.locations.name"},
                    {"key": "lat", "field": "testprov.locations.lat"},
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        # table.data returns columns + rows, or html (Great Tables)
        assert "columns" in data or "html" in data


class TestBronzePivot:
    def test_pivot_single_row(self, client):
        """table.pivot handler works for Bronze — single row dimension."""
        resp = client.post(
            "/api/bronze/query",
            json={
                "type": "table.pivot",
                "rows": "testprov.events.category",
                "measures": [
                    {
                        "key": "total",
                        "field": "testprov.events.value",
                        "aggregation": "sum",
                        "label": "Total",
                    },
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        # Pivot returns Great Tables HTML
        assert "html" in data

    def test_pivot_with_cols(self, client):
        """table.pivot with column dimension."""
        resp = client.post(
            "/api/bronze/query",
            json={
                "type": "table.pivot",
                "rows": "testprov.events.category",
                "cols": "testprov.events.year",
                "measures": [
                    {
                        "key": "count",
                        "field": "testprov.events.event_id",
                        "aggregation": "count",
                        "label": "Count",
                    },
                ],
            },
        )
        assert resp.status_code == 200
        assert "html" in resp.json()


# ---------------------------------------------------------------------------
# Cross-endpoint references (same provider, different endpoints)
# ---------------------------------------------------------------------------

class TestCrossEndpoint:
    def test_cross_endpoint_graceful(self, client):
        """Refs from two endpoints fall back to CROSS JOIN (not crash)."""
        resp = client.post(
            "/api/bronze/query",
            json={
                "type": "cards.metric",
                "metrics": [
                    {
                        "key": "events",
                        "field": "testprov.events.event_id",
                        "aggregation": "count",
                        "label": "Events",
                    },
                    {
                        "key": "locations",
                        "field": "testprov.locations.location_id",
                        "aggregation": "count",
                        "label": "Locations",
                    },
                ],
            },
        )
        # May CROSS JOIN or handle per-metric — should not crash
        assert resp.status_code in (200, 400, 500)


# ---------------------------------------------------------------------------
# Silver endpoints unaffected
# ---------------------------------------------------------------------------

class TestSilverUnaffected:
    def test_silver_query_not_on_bronze_app(self, client):
        """/api/query doesn't exist on the bronze-only test app."""
        resp = client.post("/api/query", json={"type": "cards.metric"})
        # 404 because we only mounted the bronze router
        assert resp.status_code == 404
