"""
Test Delta Lake integration with DuckDB.

Tests core Delta Lake functionality:
- Reading/writing Delta tables
- Time travel
- Merge operations
- Optimization
- Backend adapter integration
"""

import sys
from pathlib import Path

# Add repository root to Python path
REPO_ROOT = get_repo_root().resolve()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest
import pandas as pd
import tempfile
import shutil
from datetime import datetime, timedelta

try:
    from deltalake import DeltaTable, write_deltalake
    DELTA_AVAILABLE = True
except ImportError:
    DELTA_AVAILABLE = False

from de_funk.core.duckdb_connection import DuckDBConnection


@pytest.fixture
def temp_dir():
    """Create temporary directory for test data."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def sample_df():
    """Create sample DataFrame for testing."""
    return pd.DataFrame({
        'ticker': ['AAPL', 'GOOGL', 'MSFT', 'AAPL', 'GOOGL'],
        'trade_date': ['2024-01-15', '2024-01-15', '2024-01-15', '2024-01-16', '2024-01-16'],
        'close': [185.50, 150.20, 420.30, 186.20, 151.50],
        'volume': [50000000, 25000000, 30000000, 48000000, 24000000]
    })


@pytest.fixture
def duckdb_connection():
    """Create DuckDB connection with Delta support."""
    conn = DuckDBConnection(enable_delta=True)
    yield conn
    conn.stop()


class TestDuckDBConnectionDelta:
    """Test DuckDB connection Delta Lake functionality."""

    @pytest.mark.skipif(not DELTA_AVAILABLE, reason="Delta Lake not installed")
    def test_delta_extension_enabled(self, duckdb_connection):
        """Test that Delta extension is enabled."""
        assert duckdb_connection.delta_enabled is True

    def test_is_delta_table_detection(self, temp_dir, sample_df):
        """Test Delta table detection."""
        conn = DuckDBConnection(enable_delta=True)

        # Write Delta table
        delta_path = temp_dir / "test_delta"
        write_deltalake(str(delta_path), sample_df, mode='overwrite')

        # Should detect as Delta
        assert conn._is_delta_table(str(delta_path)) is True

        # Non-existent path
        assert conn._is_delta_table(str(temp_dir / "nonexistent")) is False

        # Regular directory (not Delta)
        regular_dir = temp_dir / "regular"
        regular_dir.mkdir()
        assert conn._is_delta_table(str(regular_dir)) is False

    @pytest.mark.skipif(not DELTA_AVAILABLE, reason="Delta Lake not installed")
    def test_write_delta_table_overwrite(self, duckdb_connection, temp_dir, sample_df):
        """Test writing Delta table with overwrite mode."""
        delta_path = temp_dir / "test_delta_overwrite"

        # Write data
        duckdb_connection.write_delta_table(
            sample_df,
            str(delta_path),
            mode='overwrite'
        )

        # Verify Delta table exists
        assert (delta_path / "_delta_log").exists()

        # Read back and verify
        result = duckdb_connection.read_table(str(delta_path), format='delta')
        result_df = result.df()

        assert len(result_df) == len(sample_df)
        assert list(result_df.columns) == list(sample_df.columns)

    @pytest.mark.skipif(not DELTA_AVAILABLE, reason="Delta Lake not installed")
    def test_write_delta_table_append(self, duckdb_connection, temp_dir, sample_df):
        """Test writing Delta table with append mode."""
        delta_path = temp_dir / "test_delta_append"

        # Initial write
        initial_df = sample_df.head(3)
        duckdb_connection.write_delta_table(
            initial_df,
            str(delta_path),
            mode='overwrite'
        )

        # Append more data
        append_df = sample_df.tail(2)
        duckdb_connection.write_delta_table(
            append_df,
            str(delta_path),
            mode='append'
        )

        # Read back
        result_df = duckdb_connection.read_table(str(delta_path), format='delta').df()

        # Should have all 5 rows
        assert len(result_df) == 5

    @pytest.mark.skipif(not DELTA_AVAILABLE, reason="Delta Lake not installed")
    def test_write_delta_table_merge(self, duckdb_connection, temp_dir, sample_df):
        """Test writing Delta table with merge mode (upsert)."""
        delta_path = temp_dir / "test_delta_merge"

        # Initial write
        duckdb_connection.write_delta_table(
            sample_df,
            str(delta_path),
            mode='overwrite'
        )

        # Create update data (overlapping + new)
        update_df = pd.DataFrame({
            'ticker': ['AAPL', 'TSLA'],  # AAPL exists, TSLA new
            'trade_date': ['2024-01-15', '2024-01-15'],
            'close': [185.75, 215.30],  # AAPL updated
            'volume': [51000000, 35000000]
        })

        # Merge
        duckdb_connection.write_delta_table(
            update_df,
            str(delta_path),
            mode='merge',
            merge_keys=['ticker', 'trade_date']
        )

        # Read back
        result_df = duckdb_connection.read_table(str(delta_path), format='delta').df()

        # Should have 6 rows (5 original + 1 new, with 1 updated)
        assert len(result_df) == 6

        # Check AAPL was updated
        aapl_row = result_df[
            (result_df['ticker'] == 'AAPL') &
            (result_df['trade_date'] == '2024-01-15')
        ]
        assert aapl_row['close'].values[0] == 185.75

        # Check TSLA was inserted
        tsla_rows = result_df[result_df['ticker'] == 'TSLA']
        assert len(tsla_rows) == 1

    @pytest.mark.skipif(not DELTA_AVAILABLE, reason="Delta Lake not installed")
    def test_write_delta_table_with_partitioning(self, duckdb_connection, temp_dir, sample_df):
        """Test writing Delta table with partitioning."""
        delta_path = temp_dir / "test_delta_partitioned"

        # Write with partitioning
        duckdb_connection.write_delta_table(
            sample_df,
            str(delta_path),
            mode='overwrite',
            partition_by=['ticker']
        )

        # Check partition directories exist
        assert (delta_path / "ticker=AAPL").exists()
        assert (delta_path / "ticker=GOOGL").exists()
        assert (delta_path / "ticker=MSFT").exists()

    @pytest.mark.skipif(not DELTA_AVAILABLE, reason="Delta Lake not installed")
    @pytest.mark.xfail(reason="Known PyArrow issue: Repetition level histogram size mismatch with delta-rs time travel")
    def test_read_delta_table_time_travel_version(self, duckdb_connection, temp_dir, sample_df):
        """Test reading specific version of Delta table (time travel)."""
        delta_path = temp_dir / "test_delta_timetravel"

        # Version 0: Initial write
        v0_df = sample_df.head(3)
        duckdb_connection.write_delta_table(v0_df, str(delta_path), mode='overwrite')

        # Version 1: Append
        v1_df = sample_df.tail(2)
        duckdb_connection.write_delta_table(v1_df, str(delta_path), mode='append')

        # Read version 0
        v0_result = duckdb_connection.read_table(str(delta_path), format='delta', version=0).df()
        assert len(v0_result) == 3

        # Read version 1 (current)
        v1_result = duckdb_connection.read_table(str(delta_path), format='delta', version=1).df()
        assert len(v1_result) == 5

    @pytest.mark.skipif(not DELTA_AVAILABLE, reason="Delta Lake not installed")
    def test_get_delta_table_history(self, duckdb_connection, temp_dir, sample_df):
        """Test retrieving Delta table history."""
        delta_path = temp_dir / "test_delta_history"

        # Create some history
        duckdb_connection.write_delta_table(
            sample_df.head(3),
            str(delta_path),
            mode='overwrite'
        )
        duckdb_connection.write_delta_table(
            sample_df.tail(2),
            str(delta_path),
            mode='append'
        )

        # Get history
        history = duckdb_connection.get_delta_table_history(str(delta_path))

        # Should have 2 versions
        assert len(history) >= 2
        assert 'version' in history.columns
        assert 'timestamp' in history.columns

    @pytest.mark.skipif(not DELTA_AVAILABLE, reason="Delta Lake not installed")
    def test_optimize_delta_table(self, duckdb_connection, temp_dir, sample_df):
        """Test optimizing Delta table."""
        delta_path = temp_dir / "test_delta_optimize"

        # Write data
        duckdb_connection.write_delta_table(
            sample_df,
            str(delta_path),
            mode='overwrite'
        )

        # Optimize (compact)
        duckdb_connection.optimize_delta_table(str(delta_path))

        # Table should still be readable
        result_df = duckdb_connection.read_table(str(delta_path), format='delta').df()
        assert len(result_df) == len(sample_df)

    @pytest.mark.skipif(not DELTA_AVAILABLE, reason="Delta Lake not installed")
    def test_optimize_delta_table_with_zorder(self, duckdb_connection, temp_dir, sample_df):
        """Test optimizing Delta table with z-ordering."""
        delta_path = temp_dir / "test_delta_zorder"

        # Write data
        duckdb_connection.write_delta_table(
            sample_df,
            str(delta_path),
            mode='overwrite'
        )

        # Optimize with z-order
        duckdb_connection.optimize_delta_table(
            str(delta_path),
            zorder_by=['ticker', 'trade_date']
        )

        # Table should still be readable
        result_df = duckdb_connection.read_table(str(delta_path), format='delta').df()
        assert len(result_df) == len(sample_df)

    @pytest.mark.skipif(not DELTA_AVAILABLE, reason="Delta Lake not installed")
    def test_vacuum_delta_table(self, duckdb_connection, temp_dir, sample_df):
        """Test vacuuming Delta table."""
        delta_path = temp_dir / "test_delta_vacuum"

        # Create some versions
        duckdb_connection.write_delta_table(
            sample_df,
            str(delta_path),
            mode='overwrite'
        )
        duckdb_connection.write_delta_table(
            sample_df.head(2),
            str(delta_path),
            mode='append'
        )

        # Vacuum with very short retention (0 hours for testing, disable enforcement)
        duckdb_connection.vacuum_delta_table(str(delta_path), retention_hours=0, enforce_retention=False)

        # Current version should still be readable
        result_df = duckdb_connection.read_table(str(delta_path), format='delta').df()
        assert len(result_df) > 0

    @pytest.mark.skipif(not DELTA_AVAILABLE, reason="Delta Lake not installed")
    def test_read_table_auto_detect_delta(self, duckdb_connection, temp_dir, sample_df):
        """Test auto-detection of Delta format when reading."""
        delta_path = temp_dir / "test_delta_autodetect"

        # Write Delta table
        write_deltalake(str(delta_path), sample_df, mode='overwrite')

        # Read with format='parquet' - should auto-detect Delta
        result = duckdb_connection.read_table(str(delta_path), format='parquet')
        result_df = result.df()

        assert len(result_df) == len(sample_df)


class TestDuckDBAdapterDelta:
    """Test DuckDB adapter Delta Lake integration."""

    @pytest.mark.skipif(not DELTA_AVAILABLE, reason="Delta Lake not installed")
    def test_adapter_detects_delta_table(self, temp_dir, sample_df):
        """Test that adapter detects and uses delta_scan for Delta tables."""
from de_funk.models.base.backend.duckdb_adapter import DuckDBAdapter
from de_funk.core.duckdb_connection import DuckDBConnection

        # Write Delta table
        delta_path = temp_dir / "test_adapter_delta"
        write_deltalake(str(delta_path), sample_df, mode='overwrite')

        # The adapter should detect this and use delta_scan
        # This would be tested in integration with a model
        # For now, just verify _is_delta_table works
        conn = DuckDBConnection(enable_delta=True)
        assert conn._is_delta_table(str(delta_path)) is True

    def test_adapter_supports_delta_features(self):
        """Test that adapter reports Delta Lake feature support."""
from de_funk.models.base.backend.duckdb_adapter import DuckDBAdapter
from de_funk.models.base.model import BaseModel
        from unittest.mock import Mock

        # Create mock model
        mock_model = Mock(spec=BaseModel)
        mock_model.model_cfg = {'schema': {}}

        # Create adapter
        adapter = DuckDBAdapter(connection=Mock(), model=mock_model)

        # Should support Delta features
        assert adapter.supports_feature('delta_lake') is True
        assert adapter.supports_feature('time_travel') is True


class TestDeltaLakeEndToEnd:
    """End-to-end Delta Lake workflow tests."""

    @pytest.mark.skipif(not DELTA_AVAILABLE, reason="Delta Lake not installed")
    @pytest.mark.xfail(reason="Known PyArrow issue: Repetition level histogram size mismatch with delta-rs time travel")
    def test_complete_workflow(self, duckdb_connection, temp_dir, sample_df):
        """Test complete Delta workflow: write, update, time travel, optimize."""
        delta_path = temp_dir / "test_complete_workflow"

        # 1. Initial load
        initial_df = sample_df.head(3)
        duckdb_connection.write_delta_table(
            initial_df,
            str(delta_path),
            mode='overwrite',
            partition_by=['ticker']
        )

        # 2. Append new data
        new_df = sample_df.tail(2)
        duckdb_connection.write_delta_table(
            new_df,
            str(delta_path),
            mode='append'
        )

        # 3. Update existing data
        update_df = pd.DataFrame({
            'ticker': ['AAPL'],
            'trade_date': ['2024-01-15'],
            'close': [187.00],  # Updated price
            'volume': [52000000]
        })
        duckdb_connection.write_delta_table(
            update_df,
            str(delta_path),
            mode='merge',
            merge_keys=['ticker', 'trade_date']
        )

        # 4. Query current state
        current_df = duckdb_connection.read_table(str(delta_path), format='delta').df()
        assert len(current_df) == 5

        # 5. Time travel to version 1 (after append, before update)
        v1_df = duckdb_connection.read_table(str(delta_path), format='delta', version=1).df()
        assert len(v1_df) == 5
        # Price should be old value in version 1
        aapl_v1 = v1_df[(v1_df['ticker'] == 'AAPL') & (v1_df['trade_date'] == '2024-01-15')]
        assert aapl_v1['close'].values[0] == 185.50  # Original price

        # 6. Check current has updated price
        aapl_current = current_df[(current_df['ticker'] == 'AAPL') & (current_df['trade_date'] == '2024-01-15')]
        assert aapl_current['close'].values[0] == 187.00  # Updated price

        # 7. Optimize
        duckdb_connection.optimize_delta_table(str(delta_path), zorder_by=['ticker'])

        # 8. Verify history
        history = duckdb_connection.get_delta_table_history(str(delta_path))
        assert len(history) >= 3  # overwrite + append + merge


def test_delta_not_available_graceful_handling():
    """Test graceful handling when Delta is not available."""
    # This should work even without Delta installed
    conn = DuckDBConnection(enable_delta=False)
    assert conn.delta_enabled is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
