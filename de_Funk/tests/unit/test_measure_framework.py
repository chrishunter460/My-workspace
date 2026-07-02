"""
Unit tests for measure framework.

Tests measure registry, executor, and base classes.
"""

import sys
from pathlib import Path

# Add repository root to Python path
REPO_ROOT = get_repo_root().resolve()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest
from de_funk.models.measures.base_measure import BaseMeasure, MeasureType
from de_funk.models.measures.registry import MeasureRegistry
from de_funk.models.measures.executor import MeasureExecutor
from de_funk.models.measures.simple import SimpleMeasure
from de_funk.models.measures.computed import ComputedMeasure


class TestMeasureRegistry:
    """Test measure registry."""

    def test_measure_types_enum(self):
        """Test MeasureType enum values."""
        assert MeasureType.SIMPLE.value == 'simple'
        assert MeasureType.COMPUTED.value == 'computed'
        assert MeasureType.WEIGHTED.value == 'weighted'

    def test_create_simple_measure(self):
        """Test creating simple measure from config."""
        config = {
            'name': 'test_measure',
            'source': 'fact_prices.close',
            'aggregation': 'avg',
            'data_type': 'double'
        }

        measure = MeasureRegistry.create_measure(config)

        assert isinstance(measure, SimpleMeasure)
        assert measure.name == 'test_measure'
        assert measure.source == 'fact_prices.close'
        assert measure.aggregation == 'AVG'

    def test_create_computed_measure(self):
        """Test creating computed measure from config."""
        config = {
            'name': 'market_cap',
            'type': 'computed',
            'source': 'fact_prices.close',
            'expression': 'close * volume',
            'aggregation': 'avg',
            'data_type': 'double'
        }

        measure = MeasureRegistry.create_measure(config)

        assert isinstance(measure, ComputedMeasure)
        assert measure.name == 'market_cap'
        assert measure.expression == 'close * volume'

    def test_create_measure_unknown_type(self):
        """Test error handling for unknown measure type."""
        config = {
            'name': 'bad_measure',
            'type': 'unknown',
            'source': 'fact_prices.close'
        }

        with pytest.raises(ValueError, match="Unknown measure type"):
            MeasureRegistry.create_measure(config)

    def test_get_registered_types(self):
        """Test getting registered measure types."""
        types = MeasureRegistry.get_registered_types()

        assert MeasureType.SIMPLE in types
        assert MeasureType.COMPUTED in types
        # WEIGHTED enum exists but no implementation registered

    def test_is_registered(self):
        """Test checking if measure type is registered."""
        assert MeasureRegistry.is_registered(MeasureType.SIMPLE) is True
        assert MeasureRegistry.is_registered(MeasureType.COMPUTED) is True
        # WEIGHTED enum exists but no implementation registered


class TestMeasureExecutor:
    """Test measure executor."""

    def test_executor_initialization(self, mock_model):
        """Test executor initialization."""
        executor = MeasureExecutor(mock_model, backend='duckdb')

        assert executor.model == mock_model
        assert executor.backend == 'duckdb'
        assert executor.adapter is not None

    def test_list_measures(self, mock_model):
        """Test listing available measures."""
        executor = MeasureExecutor(mock_model, backend='duckdb')
        measures = executor.list_measures()

        assert 'avg_close_price' in measures
        assert 'market_cap' in measures

    def test_get_measure_info(self, mock_model):
        """Test getting measure information."""
        executor = MeasureExecutor(mock_model, backend='duckdb')
        info = executor.get_measure_info('avg_close_price')

        assert info['name'] == 'avg_close_price'
        assert info['type'] == 'simple'
        assert info['source'] == 'fact_prices.close'
        assert info['data_type'] == 'double'

    def test_get_measure_info_missing(self, mock_model):
        """Test error handling for missing measure."""
        executor = MeasureExecutor(mock_model, backend='duckdb')

        with pytest.raises(ValueError, match="not defined"):
            executor.get_measure_info('nonexistent_measure')

    def test_explain_measure(self, mock_model):
        """Test SQL generation without execution."""
        executor = MeasureExecutor(mock_model, backend='duckdb')
        sql = executor.explain_measure('avg_close_price')

        assert isinstance(sql, str)
        assert 'SELECT' in sql
        assert 'AVG' in sql
        assert 'close' in sql


class TestBaseMeasure:
    """Test base measure functionality."""

    def test_parse_source(self):
        """Test source parsing."""
        config = {
            'name': 'test',
            'source': 'fact_prices.close',
            'data_type': 'double'
        }

        measure = SimpleMeasure(config)
        table, column = measure._parse_source()

        assert table == 'fact_prices'
        assert column == 'close'

    def test_parse_source_invalid(self):
        """Test error handling for invalid source format."""
        config = {
            'name': 'test',
            'source': 'invalid_source',  # Missing dot
            'data_type': 'double'
        }

        measure = SimpleMeasure(config)

        with pytest.raises(ValueError, match="must be in format"):
            measure._parse_source()

    def test_get_table_name(self):
        """Test getting table name from source."""
        config = {
            'name': 'test',
            'source': 'fact_prices.close',
            'data_type': 'double'
        }

        measure = SimpleMeasure(config)
        assert measure._get_table_name() == 'fact_prices'

    def test_get_column_name(self):
        """Test getting column name from source."""
        config = {
            'name': 'test',
            'source': 'fact_prices.close',
            'data_type': 'double'
        }

        measure = SimpleMeasure(config)
        assert measure._get_column_name() == 'close'


class TestSimpleMeasure:
    """Test simple measure implementation."""

    def test_simple_measure_creation(self):
        """Test creating simple measure."""
        config = {
            'name': 'avg_close',
            'source': 'fact_prices.close',
            'aggregation': 'avg',
            'data_type': 'double'
        }

        measure = SimpleMeasure(config)

        assert measure.name == 'avg_close'
        assert measure.aggregation == 'AVG'
        assert measure.source == 'fact_prices.close'

    def test_invalid_aggregation(self):
        """Test error handling for invalid aggregation."""
        config = {
            'name': 'bad_agg',
            'source': 'fact_prices.close',
            'aggregation': 'invalid',
            'data_type': 'double'
        }

        with pytest.raises(ValueError, match="Invalid aggregation"):
            SimpleMeasure(config)

    def test_to_sql(self, mock_model):
        """Test SQL generation for simple measure."""
from de_funk.models.base.backend.duckdb_adapter import DuckDBAdapter

        config = {
            'name': 'avg_close',
            'source': 'fact_prices.close',
            'aggregation': 'avg',
            'data_type': 'double'
        }

        measure = SimpleMeasure(config)
        adapter = DuckDBAdapter(mock_model.connection, mock_model)
        sql = measure.to_sql(adapter)

        assert 'AVG(close)' in sql
        assert 'WHERE close IS NOT NULL' in sql


class TestComputedMeasure:
    """Test computed measure implementation."""

    def test_computed_measure_creation(self):
        """Test creating computed measure."""
        config = {
            'name': 'market_cap',
            'source': 'fact_prices.close',
            'expression': 'close * volume',
            'aggregation': 'avg',
            'data_type': 'double'
        }

        measure = ComputedMeasure(config)

        assert measure.name == 'market_cap'
        assert measure.expression == 'close * volume'
        assert measure.aggregation == 'AVG'

    def test_missing_expression(self):
        """Test error handling for missing expression."""
        config = {
            'name': 'bad_computed',
            'source': 'fact_prices.close',
            'aggregation': 'avg',
            'data_type': 'double'
        }

        with pytest.raises(ValueError, match="requires 'expression'"):
            ComputedMeasure(config)

    def test_to_sql(self, mock_model):
        """Test SQL generation for computed measure."""
from de_funk.models.base.backend.duckdb_adapter import DuckDBAdapter

        config = {
            'name': 'market_cap',
            'source': 'fact_prices.close',
            'expression': 'close * volume',
            'aggregation': 'avg',
            'data_type': 'double'
        }

        measure = ComputedMeasure(config)
        adapter = DuckDBAdapter(mock_model.connection, mock_model)
        sql = measure.to_sql(adapter)

        assert 'AVG(close * volume)' in sql
        assert 'WHERE' in sql
