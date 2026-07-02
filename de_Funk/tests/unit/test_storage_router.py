"""Tests for StorageRouter — Phase 4."""
import pytest
from de_funk.core.storage import StorageRouter


@pytest.fixture
def router():
    return StorageRouter({
        "roots": {
            "raw": "/mnt/disk/storage/raw",
            "bronze": "/shared/storage/bronze",
            "silver": "/shared/storage/silver",
            "models": "/shared/storage/models",
        },
        "domain_roots": {
            "securities.stocks": "stocks",
            "securities.master": "securities",
        },
        "tables": {
            "calendar_seed": {"root": "bronze", "rel": "seeds/calendar"},
            "dim_calendar": {"root": "silver", "rel": "temporal/dims/dim_calendar"},
        },
    })


class TestRawPath:
    def test_raw_path(self, router):
        assert router.raw_path("alpha_vantage", "daily") == "/mnt/disk/storage/raw/alpha_vantage/daily"


class TestBronzePath:
    def test_bronze_path(self, router):
        assert router.bronze_path("alpha_vantage", "listing_status") == "/shared/storage/bronze/alpha_vantage/listing_status"


class TestSilverPath:
    def test_silver_path_default(self, router):
        assert router.silver_path("temporal") == "/shared/storage/silver/temporal"

    def test_silver_path_with_table(self, router):
        assert router.silver_path("temporal", "dims/dim_calendar") == "/shared/storage/silver/temporal/dims/dim_calendar"

    def test_silver_path_domain_override(self, router):
        assert router.silver_path("securities.stocks") == "/shared/storage/silver/stocks"

    def test_silver_path_no_override(self, router):
        path = router.silver_path("corporate.entity")
        assert path == "/shared/storage/silver/corporate/entity"


class TestModelPath:
    def test_model_path(self, router):
        assert router.model_path("arima_aapl", "v3") == "/shared/storage/models/arima_aapl/v3"

    def test_model_path_no_version(self, router):
        assert router.model_path("arima_aapl") == "/shared/storage/models/arima_aapl"


class TestResolve:
    def test_resolve_bronze_ref(self, router):
        path = router.resolve("bronze.alpha_vantage.listing_status")
        assert path == "/shared/storage/bronze/alpha_vantage/listing_status"

    def test_resolve_silver_ref(self, router):
        path = router.resolve("silver.stocks/dims/dim_stock")
        assert path == "/shared/storage/silver/stocks/dims/dim_stock"

    def test_resolve_absolute_path(self, router):
        path = router.resolve("/absolute/path/to/table")
        assert path == "/absolute/path/to/table"

    def test_resolve_named_table(self, router):
        path = router.resolve("dim_calendar")
        assert path == "/shared/storage/silver/temporal/dims/dim_calendar"

    def test_resolve_unknown_defaults_to_silver(self, router):
        path = router.resolve("some_unknown_table")
        assert path == "/shared/storage/silver/some_unknown_table"


class TestProperties:
    def test_properties(self, router):
        assert router.silver_root == "/shared/storage/silver"
        assert router.bronze_root == "/shared/storage/bronze"
        assert router.raw_root == "/mnt/disk/storage/raw"
        assert router.models_root == "/shared/storage/models"


class TestDefaultConfig:
    def test_empty_config(self):
        router = StorageRouter({})
        assert router.silver_root == "storage/silver"
        assert router.bronze_root == "storage/bronze"
