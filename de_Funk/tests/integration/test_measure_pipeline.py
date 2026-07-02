"""
Integration tests for complete measure pipeline.

Tests end-to-end measure calculation from config to results.
"""

import pytest
import pandas as pd
import duckdb
from pathlib import Path


class TestSimpleMeasurePipeline:
    """Test simple measure end-to-end pipeline."""

    def test_calculate_simple_measure(self, mock_model, sample_price_data):
        """Test calculating simple measure through full pipeline."""
        # Use calculate_measure method
        result = mock_model.calculate_measure(
            'avg_close_price',
            entity_column='ticker'
        )

        # Verify result
        assert result is not None
        assert result.backend == 'duckdb'
        assert isinstance(result.data, pd.DataFrame)
        assert 'ticker' in result.data.columns
        assert 'measure_value' in result.data.columns
        assert len(result.data) > 0
        assert result.query_time_ms > 0

    def test_calculate_simple_measure_with_limit(self, mock_model):
        """Test simple measure with limit."""
        result = mock_model.calculate_measure(
            'avg_close_price',
            entity_column='ticker',
            limit=2
        )

        assert len(result.data) <= 2


class TestComputedMeasurePipeline:
    """Test computed measure end-to-end pipeline."""

    def test_calculate_computed_measure(self, mock_model):
        """Test calculating computed measure through full pipeline."""
        result = mock_model.calculate_measure(
            'market_cap',
            entity_column='ticker'
        )

        assert result is not None
        assert isinstance(result.data, pd.DataFrame)
        assert 'ticker' in result.data.columns
        assert 'measure_value' in result.data.columns

        # Verify computation: market_cap should be close * volume averaged
        # Values should be larger than just close prices
        assert result.data['measure_value'].min() > 1000


class TestWeightedMeasurePipeline:
    """Test weighted measure end-to-end pipeline."""

    def test_calculate_weighted_measure(self, mock_model):
        """Test calculating weighted measure through full pipeline."""
        result = mock_model.calculate_measure('volume_weighted_index')

        assert result is not None
        assert isinstance(result.data, pd.DataFrame)
        assert 'trade_date' in result.data.columns
        assert 'weighted_value' in result.data.columns
        assert 'entity_count' in result.data.columns

        # Should have one row per trade date
        assert len(result.data) == 2  # 2024-01-01 and 2024-01-02

        # Weighted values should be reasonable
        assert result.data['weighted_value'].min() > 0
        assert result.data['entity_count'].min() > 0


class TestCrossModelMeasures:
    """Test measures that reference multiple models."""

    def test_measure_with_cross_model_reference(self, temp_dir, sample_price_data, sample_company_data):
        """Test measure that joins across models."""
        # This would test ETF holdings-based measures
        # Requires setting up multiple models
        # Placeholder for now
        pass


class TestBackendComparison:
    """Compare results between backends (when Spark available)."""

    def test_duckdb_results(self, mock_model):
        """Test DuckDB backend results."""
        result = mock_model.calculate_measure(
            'avg_close_price',
            entity_column='ticker'
        )

        assert result.backend == 'duckdb'
        assert len(result.data) > 0

        # Save results for comparison
        duckdb_results = result.data.sort_values('ticker').reset_index(drop=True)

        # Basic sanity checks
        assert duckdb_results['measure_value'].notna().all()
        assert (duckdb_results['measure_value'] > 0).all()

    # Note: Spark tests would be added here if PySpark is available
    # def test_spark_results(self, spark_model):
    #     result = spark_model.calculate_measure(...)
    #     assert result.backend == 'spark'


class TestMeasureWithComplexFilters:
    """Test measures with various filter combinations."""

    def test_measure_with_date_filter(self, mock_model):
        """Test measure with date range filter."""
        # This would require adding date filters to the pipeline
        # Currently filters aren't fully implemented in executor
        # Placeholder for demonstration
        pass


class TestErrorHandling:
    """Test error handling in pipeline."""

    def test_invalid_measure_name(self, mock_model):
        """Test error for invalid measure name."""
        with pytest.raises(ValueError, match="not defined"):
            mock_model.calculate_measure('nonexistent_measure')

    def test_invalid_backend(self, simple_model_config, storage_cfg, duckdb_connection):
        """Test error for invalid backend."""
from de_funk.models.base.model import BaseModel

        model = BaseModel(duckdb_connection, storage_cfg, simple_model_config)

        # Force invalid backend
        model._backend = 'invalid'

        with pytest.raises(ValueError, match="Unsupported backend"):
            model.calculate_measure('avg_close_price')


class TestPerformance:
    """Test performance characteristics."""

    def test_measure_execution_time(self, mock_model):
        """Test that measure execution completes in reasonable time."""
        import time

        start = time.time()
        result = mock_model.calculate_measure('avg_close_price', entity_column='ticker')
        elapsed = time.time() - start

        # Should complete in under 1 second for small dataset
        assert elapsed < 1.0

        # Result should include timing
        assert result.query_time_ms > 0
        assert result.query_time_ms < 1000  # Less than 1 second

    def test_sql_generation_performance(self, mock_model):
        """Test SQL generation performance."""
        import time

        # SQL generation should be very fast
        start = time.time()
        sql = mock_model.measures.explain_measure('volume_weighted_index')
        elapsed = time.time() - start

        assert elapsed < 0.1  # Should be nearly instant
        assert len(sql) > 0


class TestResultConsistency:
    """Test that results are consistent across multiple runs."""

    def test_repeated_execution_consistency(self, mock_model):
        """Test that repeated execution produces same results."""
        result1 = mock_model.calculate_measure('avg_close_price', entity_column='ticker')
        result2 = mock_model.calculate_measure('avg_close_price', entity_column='ticker')

        # Results should be identical
        pd.testing.assert_frame_equal(
            result1.data.sort_values('ticker').reset_index(drop=True),
            result2.data.sort_values('ticker').reset_index(drop=True)
        )

    def test_sql_generation_consistency(self, mock_model):
        """Test that SQL generation is deterministic."""
        sql1 = mock_model.measures.explain_measure('volume_weighted_index')
        sql2 = mock_model.measures.explain_measure('volume_weighted_index')

        # SQL should be identical
        assert sql1 == sql2
