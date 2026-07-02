"""
Pytest configuration and shared fixtures.

Provides common test fixtures for backend adapters, models, and test data.
"""

import sys
from pathlib import Path

# Bootstrap repo imports using centralized repo discovery
repo_root = Path(__file__).resolve().parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

# Now we can use the unified config system
from de_funk.utils.repo import setup_repo_imports
setup_repo_imports()

import pytest
import tempfile
import yaml
import pandas as pd
import duckdb


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_price_data():
    """Generate sample price data for testing."""
    return pd.DataFrame({
        'trade_date': ['2024-01-01', '2024-01-01', '2024-01-01', '2024-01-02', '2024-01-02'],
        'ticker': ['AAPL', 'MSFT', 'GOOGL', 'AAPL', 'MSFT'],
        'open': [150.0, 350.0, 120.0, 152.0, 355.0],
        'high': [155.0, 360.0, 125.0, 157.0, 365.0],
        'low': [149.0, 348.0, 119.0, 151.0, 353.0],
        'close': [153.0, 358.0, 123.0, 156.0, 362.0],
        'volume': [1000000, 500000, 750000, 1100000, 520000],
        'volume_weighted': [152.5, 356.5, 122.5, 155.5, 360.5]
    })


@pytest.fixture
def sample_company_data():
    """Generate sample company dimension data."""
    return pd.DataFrame({
        'ticker': ['AAPL', 'MSFT', 'GOOGL'],
        'company_name': ['Apple Inc.', 'Microsoft Corp.', 'Alphabet Inc.'],
        'exchange_code': ['NASDAQ', 'NASDAQ', 'NASDAQ'],
        'company_id': ['sha1_aapl', 'sha1_msft', 'sha1_googl']
    })


@pytest.fixture
def sample_etf_holdings():
    """Generate sample ETF holdings data."""
    return pd.DataFrame({
        'etf_ticker': ['SPY', 'SPY', 'SPY'],
        'holding_ticker': ['AAPL', 'MSFT', 'GOOGL'],
        'as_of_date': ['2024-01-01', '2024-01-01', '2024-01-01'],
        'weight_percent': [6.5, 6.0, 3.5],  # Percentages
        'shares_held': [1000000, 900000, 500000],
        'market_value': [153000000.0, 322200000.0, 61500000.0]
    })


@pytest.fixture
def simple_model_config():
    """Generate simple model configuration for testing."""
    return {
        'model': 'test_model',
        'version': 1,
        'storage': {
            'root': 'storage/silver/test',
            'format': 'parquet'
        },
        'schema': {
            'dimensions': {
                'dim_company': {
                    'path': 'dims/dim_company',
                    'columns': {
                        'ticker': 'string',
                        'company_name': 'string',
                        'exchange_code': 'string'
                    },
                    'primary_key': ['ticker']
                }
            },
            'facts': {
                'fact_prices': {
                    'path': 'facts/fact_prices',
                    'columns': {
                        'trade_date': 'date',
                        'ticker': 'string',
                        'close': 'double',
                        'volume': 'long'
                    }
                    # Note: partitions are defined in storage.json, not here
                }
            }
        },
        'measures': {
            'avg_close_price': {
                'source': 'fact_prices.close',
                'aggregation': 'avg',
                'data_type': 'double'
            },
            'market_cap': {
                'type': 'computed',
                'source': 'fact_prices.close',
                'expression': 'close * volume',
                'aggregation': 'avg',
                'data_type': 'double'
            },
            'volume_weighted_index': {
                'type': 'weighted',
                'source': 'fact_prices.close',
                'weighting_method': 'volume',
                'group_by': ['trade_date'],
                'data_type': 'double'
            }
        }
    }


@pytest.fixture
def duckdb_connection(temp_dir, sample_price_data):
    """Create DuckDB connection with sample data."""
    conn = duckdb.connect(':memory:')

    # Create sample table
    conn.execute("CREATE TABLE fact_prices AS SELECT * FROM sample_price_data", {
        'sample_price_data': sample_price_data
    })

    yield conn
    conn.close()


@pytest.fixture
def mock_model(simple_model_config, duckdb_connection, temp_dir):
    """Create a mock model for testing."""
    from de_funk.models.base.model import BaseModel

    storage_cfg = {
        'roots': {
            'silver': str(temp_dir / 'silver'),
            'bronze': str(temp_dir / 'bronze')
        },
        'tables': {}
    }

    model = BaseModel(
        connection=duckdb_connection,
        storage_cfg=storage_cfg,
        model_cfg=simple_model_config
    )

    return model


@pytest.fixture
def storage_cfg(temp_dir):
    """Generate storage configuration."""
    return {
        'roots': {
            'silver': str(temp_dir / 'silver'),
            'bronze': str(temp_dir / 'bronze')
        },
        'tables': {}
    }
