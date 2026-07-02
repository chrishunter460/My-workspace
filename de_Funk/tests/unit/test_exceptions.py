#!/usr/bin/env python
"""
Unit tests for the custom exception hierarchy.

Tests:
- Exception inheritance
- Error details and recovery hints
- String formatting
- Specific exception types

Usage:
    python -m pytest scripts/test/unit/test_exceptions.py -v
    # or directly:
    python scripts/test/unit/test_exceptions.py
"""

import sys
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from de_funk.core.exceptions import (
    DeFunkError,
    ConfigurationError,
    MissingConfigError,
    InvalidConfigError,
    PipelineError,
    IngestionError,
    RateLimitError,
    TransformationError,
    ModelError,
    ModelNotFoundError,
    TableNotFoundError,
    MeasureError,
    DependencyError,
    QueryError,
    FilterError,
    JoinError,
    StorageError,
    DataNotFoundError,
    WriteError,
    ForecastError,
    InsufficientDataError,
    ModelTrainingError,
)


class TestDeFunkError:
    """Tests for base DeFunkError class."""

    def test_basic_message(self):
        """Test basic error message."""
        error = DeFunkError("Test error message")
        assert str(error) == "Test error message"
        assert error.message == "Test error message"

    def test_with_details(self):
        """Test error with details."""
        error = DeFunkError("Error", details={"key": "value"})
        assert error.details == {"key": "value"}

    def test_with_recovery_hint(self):
        """Test error with recovery hint."""
        error = DeFunkError("Error", recovery_hint="Try this fix")
        assert error.recovery_hint == "Try this fix"
        assert "Try this fix" in str(error)

    def test_repr(self):
        """Test repr output."""
        error = DeFunkError("Error", details={"k": "v"}, recovery_hint="hint")
        repr_str = repr(error)
        assert "DeFunkError" in repr_str
        assert "Error" in repr_str


class TestConfigurationErrors:
    """Tests for configuration-related exceptions."""

    def test_configuration_error_inheritance(self):
        """Test ConfigurationError inherits from DeFunkError."""
        error = ConfigurationError("Config error")
        assert isinstance(error, DeFunkError)

    def test_missing_config_error(self):
        """Test MissingConfigError."""
        error = MissingConfigError("API_KEY", config_file="settings.json")

        assert "API_KEY" in str(error)
        assert error.config_key == "API_KEY"
        assert error.config_file == "settings.json"
        assert error.details["key"] == "API_KEY"
        assert "Add 'API_KEY'" in error.recovery_hint

    def test_invalid_config_error(self):
        """Test InvalidConfigError."""
        error = InvalidConfigError("port", "invalid", "integer between 1-65535")

        assert "port" in str(error)
        assert error.config_key == "port"
        assert error.value == "invalid"
        assert error.expected == "integer between 1-65535"


class TestPipelineErrors:
    """Tests for pipeline-related exceptions."""

    def test_pipeline_error_inheritance(self):
        """Test PipelineError inherits from DeFunkError."""
        error = PipelineError("Pipeline failed")
        assert isinstance(error, DeFunkError)

    def test_ingestion_error(self):
        """Test IngestionError."""
        error = IngestionError("alpha_vantage", "/prices", "Connection refused")

        assert "alpha_vantage" in str(error)
        assert "/prices" in str(error)
        assert error.provider == "alpha_vantage"
        assert error.endpoint == "/prices"
        assert "API credentials" in error.recovery_hint

    def test_rate_limit_error(self):
        """Test RateLimitError."""
        error = RateLimitError("alpha_vantage", retry_after=60)

        assert "Rate limit" in str(error)
        assert error.provider == "alpha_vantage"
        assert error.retry_after == 60
        assert "60" in error.recovery_hint

    def test_transformation_error(self):
        """Test TransformationError."""
        error = TransformationError("normalize", "Invalid schema", record_count=100)

        assert "normalize" in str(error)
        assert error.stage == "normalize"
        assert error.error == "Invalid schema"
        assert error.record_count == 100


class TestModelErrors:
    """Tests for model-related exceptions."""

    def test_model_error_inheritance(self):
        """Test ModelError inherits from DeFunkError."""
        error = ModelError("Model error")
        assert isinstance(error, DeFunkError)

    def test_model_not_found_error(self):
        """Test ModelNotFoundError."""
        error = ModelNotFoundError("stocks", available_models=["core", "company"])

        assert "stocks" in str(error)
        assert error.model_name == "stocks"
        assert error.available_models == ["core", "company"]
        assert "core, company" in error.recovery_hint

    def test_table_not_found_error(self):
        """Test TableNotFoundError."""
        error = TableNotFoundError("stocks", "dim_unknown", ["dim_stock", "fact_prices"])

        assert "dim_unknown" in str(error)
        assert error.model_name == "stocks"
        assert error.table_name == "dim_unknown"
        assert "dim_stock" in error.recovery_hint

    def test_measure_error(self):
        """Test MeasureError."""
        error = MeasureError("avg_price", "Division by zero", model_name="stocks")

        assert "avg_price" in str(error)
        assert error.measure_name == "avg_price"
        assert error.model_name == "stocks"

    def test_dependency_error(self):
        """Test DependencyError."""
        error = DependencyError("stocks", ["core", "company"])

        assert "stocks" in str(error)
        assert "core" in str(error)
        assert error.model_name == "stocks"
        assert error.missing_deps == ["core", "company"]
        assert "Build dependent" in error.recovery_hint


class TestQueryErrors:
    """Tests for query-related exceptions."""

    def test_query_error_inheritance(self):
        """Test QueryError inherits from DeFunkError."""
        error = QueryError("Query failed")
        assert isinstance(error, DeFunkError)

    def test_filter_error(self):
        """Test FilterError."""
        filter_spec = {"column": "date", "operator": "invalid"}
        error = FilterError(filter_spec, "Unknown operator: invalid")

        assert "Invalid filter" in str(error)
        assert error.filter_spec == filter_spec
        assert error.error == "Unknown operator: invalid"

    def test_join_error(self):
        """Test JoinError."""
        error = JoinError("stocks.dim_stock", "company.dim_company", "No common columns")

        assert "dim_stock" in str(error)
        assert "dim_company" in str(error)
        assert error.left_table == "stocks.dim_stock"
        assert error.right_table == "company.dim_company"


class TestStorageErrors:
    """Tests for storage-related exceptions."""

    def test_storage_error_inheritance(self):
        """Test StorageError inherits from DeFunkError."""
        error = StorageError("Storage error")
        assert isinstance(error, DeFunkError)

    def test_data_not_found_error(self):
        """Test DataNotFoundError."""
        error = DataNotFoundError("/storage/silver/stocks/dim_stock", table="dim_stock")

        assert "dim_stock" in str(error)
        assert error.path == "/storage/silver/stocks/dim_stock"
        assert error.table == "dim_stock"
        assert "ingestion pipeline" in error.recovery_hint

    def test_write_error(self):
        """Test WriteError."""
        error = WriteError("/storage/bronze/data", "Permission denied")

        assert "Permission denied" in str(error)
        assert error.path == "/storage/bronze/data"
        assert "disk space" in error.recovery_hint


class TestForecastErrors:
    """Tests for forecast-related exceptions."""

    def test_forecast_error_inheritance(self):
        """Test ForecastError inherits from DeFunkError."""
        error = ForecastError("Forecast error")
        assert isinstance(error, DeFunkError)

    def test_insufficient_data_error(self):
        """Test InsufficientDataError."""
        error = InsufficientDataError(required=252, available=100, ticker="AAPL")

        assert "252" in str(error)
        assert "100" in str(error)
        assert "AAPL" in str(error)
        assert error.required == 252
        assert error.available == 100
        assert error.ticker == "AAPL"

    def test_model_training_error(self):
        """Test ModelTrainingError."""
        error = ModelTrainingError("ARIMA", "Convergence failed", ticker="MSFT")

        assert "ARIMA" in str(error)
        assert "Convergence" in str(error)
        assert error.model_type == "ARIMA"
        assert error.ticker == "MSFT"


class TestExceptionChaining:
    """Tests for exception chaining."""

    def test_exception_chaining(self):
        """Test that exceptions can be properly chained."""
        try:
            try:
                raise ValueError("Original error")
            except ValueError as e:
                raise IngestionError("provider", "/endpoint", "Failed") from e
        except IngestionError as e:
            assert e.__cause__ is not None
            assert isinstance(e.__cause__, ValueError)


class TestExceptionHierarchy:
    """Tests for proper exception hierarchy."""

    def test_all_exceptions_inherit_from_defunk_error(self):
        """Test that all custom exceptions inherit from DeFunkError."""
        exceptions = [
            ConfigurationError("test"),
            MissingConfigError("key"),
            InvalidConfigError("key", "value", "expected"),
            PipelineError("test"),
            IngestionError("prov", "ep", "err"),
            RateLimitError("prov"),
            TransformationError("stage", "err"),
            ModelError("test"),
            ModelNotFoundError("model"),
            TableNotFoundError("model", "table"),
            MeasureError("measure", "err"),
            DependencyError("model", ["dep"]),
            QueryError("test"),
            FilterError({}, "err"),
            JoinError("left", "right", "err"),
            StorageError("test"),
            DataNotFoundError("/path"),
            WriteError("/path", "err"),
            ForecastError("test"),
            InsufficientDataError(100, 50),
            ModelTrainingError("type", "err"),
        ]

        for exc in exceptions:
            assert isinstance(exc, DeFunkError), f"{type(exc).__name__} should inherit from DeFunkError"


def run_tests():
    """Run all tests and print results."""
    import traceback

    test_classes = [
        TestDeFunkError,
        TestConfigurationErrors,
        TestPipelineErrors,
        TestModelErrors,
        TestQueryErrors,
        TestStorageErrors,
        TestForecastErrors,
        TestExceptionChaining,
        TestExceptionHierarchy,
    ]

    passed = 0
    failed = 0
    errors = []

    for test_class in test_classes:
        instance = test_class()
        for method_name in dir(instance):
            if method_name.startswith("test_"):
                try:
                    method = getattr(instance, method_name)
                    method()
                    print(f"  ✓ {test_class.__name__}.{method_name}")
                    passed += 1
                except Exception as e:
                    print(f"  ✗ {test_class.__name__}.{method_name}: {e}")
                    errors.append((test_class.__name__, method_name, traceback.format_exc()))
                    failed += 1

    print()
    print(f"Results: {passed} passed, {failed} failed")

    if errors:
        print("\nFailure details:")
        for cls, method, tb in errors:
            print(f"\n{cls}.{method}:")
            print(tb)

    return failed == 0


if __name__ == "__main__":
    try:
        import pytest
        sys.exit(pytest.main([__file__, "-v"]))
    except ImportError:
        print("Running tests without pytest...")
        print()
        success = run_tests()
        sys.exit(0 if success else 1)
