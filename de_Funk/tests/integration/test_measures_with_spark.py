"""
Test suite for applying measures to Spark tables with real data.

Demonstrates:
- Loading measure definitions from model configs
- Applying measures to Spark DataFrames
- Aggregating data using measure specifications
- Testing with 20-ticker sample
- Cross-model measure usage

Run:
    pytest tests/test_measures_with_spark.py -v
    # Or run directly:
    python tests/test_measures_with_spark.py
"""

from __future__ import annotations
import sys
from pathlib import Path

# Add repository root to Python path
REPO_ROOT = get_repo_root().resolve()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest
from datetime import date, timedelta
from pyspark.sql import functions as F
from pyspark.sql import SparkSession

from de_funk.core.context import RepoContext
from de_funk.models.api.session import UniversalSession
from de_funk.models.registry import ModelRegistry


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture(scope="module")
def spark():
    """Create Spark session for tests."""
    from pyspark.sql import SparkSession
    spark = SparkSession.builder \
        .appName("MeasuresTest") \
        .master("local[2]") \
        .config("spark.sql.shuffle.partitions", "2") \
        .getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    yield spark
    spark.stop()


@pytest.fixture(scope="module")
def ctx():
    """Get RepoContext."""
    return RepoContext.from_repo_root()


@pytest.fixture(scope="module")
def session(ctx):
    """Create UniversalSession."""
    # Note: 'company' model is deprecated but kept for backward compatibility
    return UniversalSession(
        connection=ctx.connection,
        storage_cfg=ctx.storage,
        repo_root=REPO_ROOT,
        models=['core', 'company', 'equity', 'corporate', 'forecast']
    )


@pytest.fixture(scope="module")
def registry():
    """Get ModelRegistry."""
    return ModelRegistry(str(REPO_ROOT / "configs" / "models"))


@pytest.fixture
def sample_tickers():
    """Sample of 20 major tickers for testing."""
    return [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
        "META", "TSLA", "BRK.B", "JPM", "V",
        "JNJ", "WMT", "PG", "MA", "HD",
        "DIS", "BAC", "ADBE", "NFLX", "CRM"
    ]


@pytest.fixture
def date_range():
    """Sample date range for testing."""
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    return start_date.isoformat(), end_date.isoformat()


# ============================================================
# MEASURE LOADING TESTS
# ============================================================

class TestMeasureLoading:
    """Test loading measure definitions from configs."""

    def test_load_company_measures(self, registry):
        """Test loading measures from company model config."""
        config = registry.get_model_config('company')
        measures = config.get('measures', {})

        assert len(measures) > 0, "Company model should have measures"

        # Check specific measures exist
        assert 'avg_close_price' in measures
        assert 'total_volume' in measures
        assert 'market_cap' in measures

        # Validate measure structure
        avg_close = measures['avg_close_price']
        assert 'description' in avg_close
        assert 'aggregation' in avg_close
        assert avg_close['aggregation'] == 'avg'
        assert avg_close['data_type'] == 'double'

        print(f"\n✓ Loaded {len(measures)} measures from company model")
        for name, spec in measures.items():
            print(f"  - {name}: {spec['description']}")

    def test_load_equity_measures(self, registry):
        """Test loading measures from equity model config."""
        config = registry.get_model_config('equity')
        measures = config.get('measures', {})

        assert len(measures) > 0, "Equity model should have measures"

        # Check technical indicators
        if 'avg_rsi' in measures:
            rsi = measures['avg_rsi']
            assert rsi['aggregation'] == 'avg'
            assert 'technical' in rsi.get('tags', [])

        print(f"\n✓ Loaded {len(measures)} measures from equity model")

    def test_load_forecast_measures(self, registry):
        """Test loading measures from forecast model config."""
        config = registry.get_model_config('forecast')
        measures = config.get('measures', {})

        assert len(measures) > 0, "Forecast model should have measures"

        # Check forecast accuracy measures
        assert 'avg_forecast_error' in measures
        assert 'avg_forecast_mape' in measures

        mape = measures['avg_forecast_mape']
        assert mape['aggregation'] == 'avg'
        assert '%' in mape.get('format', '')

        print(f"\n✓ Loaded {len(measures)} measures from forecast model")

    def test_all_models_have_measure_metadata(self, registry):
        """Verify all models have proper measure metadata."""
        models = ['company', 'equity', 'corporate', 'forecast']

        for model_name in models:
            config = registry.get_model_config(model_name)
            measures = config.get('measures', {})

            for measure_name, spec in measures.items():
                # All measures should have these fields
                assert 'description' in spec, f"{model_name}.{measure_name} missing description"
                assert 'aggregation' in spec, f"{model_name}.{measure_name} missing aggregation"
                assert 'data_type' in spec, f"{model_name}.{measure_name} missing data_type"

                # Aggregation should be valid
                valid_aggs = ['avg', 'sum', 'count', 'count_distinct', 'max', 'min', 'stddev', 'first']
                assert spec['aggregation'] in valid_aggs, \
                    f"{model_name}.{measure_name} has invalid aggregation: {spec['aggregation']}"

        print("\n✓ All models have valid measure metadata")


# ============================================================
# COMPANY MODEL MEASURE TESTS
# ============================================================

class TestCompanyMeasures:
    """Test applying company model measures to real data."""

    def test_avg_close_price_by_ticker(self, session, sample_tickers, date_range):
        """Test average closing price measure by ticker."""
        start_date, end_date = date_range

        # Get price data
        prices_df = session.get_table('company', 'fact_prices')

        # Filter to sample tickers and date range
        filtered = prices_df.filter(
            (F.col('ticker').isin(sample_tickers)) &
            (F.col('trade_date').between(start_date, end_date))
        )

        # Apply measure: average closing price
        result = filtered.groupBy('ticker').agg(
            F.avg('close').alias('avg_close_price'),
            F.count('*').alias('trading_days')
        ).orderBy(F.desc('avg_close_price'))

        # Collect results
        data = result.collect()

        assert len(data) > 0, "Should have price data for sample tickers"

        print(f"\n✓ Average Closing Price by Ticker ({len(data)} tickers)")
        print(f"{'Ticker':<10} {'Avg Close':>12} {'Trading Days':>15}")
        print("-" * 40)
        for row in data[:10]:
            print(f"{row.ticker:<10} ${row.avg_close_price:>11,.2f} {row.trading_days:>15,}")

    def test_total_volume_by_ticker(self, session, sample_tickers, date_range):
        """Test total volume measure by ticker."""
        start_date, end_date = date_range

        prices_df = session.get_table('company', 'fact_prices')

        result = prices_df.filter(
            (F.col('ticker').isin(sample_tickers)) &
            (F.col('trade_date').between(start_date, end_date))
        ).groupBy('ticker').agg(
            F.sum('volume').alias('total_volume'),
            F.avg('volume').alias('avg_daily_volume')
        ).orderBy(F.desc('total_volume'))

        data = result.collect()

        assert len(data) > 0, "Should have volume data"

        print(f"\n✓ Total Volume by Ticker ({len(data)} tickers)")
        print(f"{'Ticker':<10} {'Total Volume':>15} {'Avg Daily':>15}")
        print("-" * 42)
        for row in data[:10]:
            print(f"{row.ticker:<10} {row.total_volume:>15,} {row.avg_daily_volume:>15,.0f}")

    def test_market_cap_proxy(self, session, sample_tickers, date_range):
        """Test market cap proxy measure (close * volume)."""
        start_date, end_date = date_range

        prices_df = session.get_table('company', 'fact_prices')

        # Apply computed measure
        result = prices_df.filter(
            (F.col('ticker').isin(sample_tickers)) &
            (F.col('trade_date').between(start_date, end_date))
        ).withColumn(
            'market_cap_proxy', F.col('close') * F.col('volume')
        ).groupBy('ticker').agg(
            F.avg('market_cap_proxy').alias('avg_market_cap_proxy')
        ).orderBy(F.desc('avg_market_cap_proxy'))

        data = result.collect()

        assert len(data) > 0, "Should have market cap data"

        print(f"\n✓ Market Cap Proxy by Ticker ({len(data)} tickers)")
        print(f"{'Ticker':<10} {'Avg Market Cap Proxy':>25}")
        print("-" * 37)
        for row in data[:10]:
            print(f"{row.ticker:<10} ${row.avg_market_cap_proxy:>24,.2f}")

    def test_price_volatility(self, session, sample_tickers, date_range):
        """Test price volatility measure (stddev of close)."""
        start_date, end_date = date_range

        prices_df = session.get_table('company', 'fact_prices')

        result = prices_df.filter(
            (F.col('ticker').isin(sample_tickers)) &
            (F.col('trade_date').between(start_date, end_date))
        ).groupBy('ticker').agg(
            F.stddev('close').alias('price_volatility'),
            F.avg('close').alias('avg_price'),
            (F.stddev('close') / F.avg('close') * 100).alias('volatility_pct')
        ).orderBy(F.desc('volatility_pct'))

        data = result.collect()

        assert len(data) > 0, "Should have volatility data"

        print(f"\n✓ Price Volatility by Ticker ({len(data)} tickers)")
        print(f"{'Ticker':<10} {'Avg Price':>12} {'Volatility':>12} {'Vol %':>8}")
        print("-" * 45)
        for row in data[:10]:
            print(f"{row.ticker:<10} ${row.avg_price:>11,.2f} ${row.price_volatility:>11,.2f} {row.volatility_pct:>7,.2f}%")

    def test_daily_range_measure(self, session, sample_tickers, date_range):
        """Test average daily range measure (high - low)."""
        start_date, end_date = date_range

        prices_df = session.get_table('company', 'fact_prices')

        result = prices_df.filter(
            (F.col('ticker').isin(sample_tickers)) &
            (F.col('trade_date').between(start_date, end_date))
        ).withColumn(
            'daily_range', F.col('high') - F.col('low')
        ).groupBy('ticker').agg(
            F.avg('daily_range').alias('avg_daily_range'),
            F.avg('close').alias('avg_close'),
            (F.avg(F.col('high') - F.col('low')) / F.avg('close') * 100).alias('range_pct')
        ).orderBy(F.desc('avg_daily_range'))

        data = result.collect()

        assert len(data) > 0, "Should have range data"

        print(f"\n✓ Average Daily Range by Ticker ({len(data)} tickers)")
        print(f"{'Ticker':<10} {'Avg Range':>12} {'Range %':>10}")
        print("-" * 35)
        for row in data[:10]:
            print(f"{row.ticker:<10} ${row.avg_daily_range:>11,.2f} {row.range_pct:>9,.2f}%")


# ============================================================
# TIME-BASED AGGREGATION TESTS
# ============================================================

class TestTimeBasedMeasures:
    """Test measures aggregated by time periods."""

    def test_monthly_avg_price(self, session, sample_tickers, date_range):
        """Test average price by month."""
        start_date, end_date = date_range

        prices_df = session.get_table('company', 'fact_prices')

        result = prices_df.filter(
            (F.col('ticker').isin(sample_tickers[:5])) &  # Just 5 tickers
            (F.col('trade_date').between(start_date, end_date))
        ).withColumn(
            'year_month', F.date_format('trade_date', 'yyyy-MM')
        ).groupBy('ticker', 'year_month').agg(
            F.avg('close').alias('avg_close'),
            F.sum('volume').alias('total_volume'),
            F.count('*').alias('trading_days')
        ).orderBy('ticker', 'year_month')

        data = result.collect()

        assert len(data) > 0, "Should have monthly data"

        print(f"\n✓ Monthly Aggregated Measures ({len(data)} ticker-months)")
        print(f"{'Ticker':<10} {'Month':<10} {'Avg Close':>12} {'Total Vol':>15} {'Days':>6}")
        print("-" * 57)
        for row in data[:15]:
            print(f"{row.ticker:<10} {row.year_month:<10} ${row.avg_close:>11,.2f} {row.total_volume:>15,} {row.trading_days:>6}")

    def test_weekly_measures(self, session, sample_tickers, date_range):
        """Test measures aggregated by week."""
        start_date, end_date = date_range

        prices_df = session.get_table('company', 'fact_prices')

        result = prices_df.filter(
            (F.col('ticker').isin(sample_tickers[:3])) &
            (F.col('trade_date').between(start_date, end_date))
        ).withColumn(
            'week', F.weekofyear('trade_date')
        ).groupBy('ticker', 'week').agg(
            F.first('close').alias('open_price'),  # First of week
            F.last('close').alias('close_price'),  # Last of week
            F.max('high').alias('week_high'),
            F.min('low').alias('week_low'),
            F.sum('volume').alias('week_volume')
        ).orderBy('ticker', 'week')

        data = result.collect()

        print(f"\n✓ Weekly OHLC Measures ({len(data)} ticker-weeks)")
        print(f"{'Ticker':<10} {'Week':>4} {'Open':>10} {'Close':>10} {'High':>10} {'Low':>10}")
        print("-" * 58)
        for row in data[:10]:
            print(f"{row.ticker:<10} {row.week:>4} ${row.open_price:>9,.2f} ${row.close_price:>9,.2f} "
                  f"${row.week_high:>9,.2f} ${row.week_low:>9,.2f}")


# ============================================================
# CROSS-MODEL MEASURE TESTS
# ============================================================

class TestCrossModelMeasures:
    """Test measures that combine data from multiple models."""

    def test_prices_with_calendar_measures(self, session, sample_tickers, date_range):
        """Test measures joined with calendar dimensions."""
        start_date, end_date = date_range

        # Get prices with calendar attributes
        prices_df = session.get_table(
            'company',
            'fact_prices',
            required_columns=['ticker', 'trade_date', 'close', 'day_of_week', 'is_weekend']
        )

        result = prices_df.filter(
            (F.col('ticker').isin(sample_tickers[:10])) &
            (F.col('trade_date').between(start_date, end_date))
        ).groupBy('ticker', 'day_of_week').agg(
            F.avg('close').alias('avg_close'),
            F.count('*').alias('trading_days')
        ).orderBy('ticker', 'day_of_week')

        data = result.collect()

        print(f"\n✓ Average Price by Day of Week ({len(data)} ticker-days)")
        print(f"{'Ticker':<10} {'Day':>10} {'Avg Close':>12} {'Days':>6}")
        print("-" * 42)
        for row in data[:20]:
            print(f"{row.ticker:<10} {row.day_of_week:>10} ${row.avg_close:>11,.2f} {row.trading_days:>6}")

    def test_company_count_by_exchange(self, session):
        """Test company count measure grouped by exchange."""
        # Get companies with exchange info
        companies_df = session.get_table(
            'company',
            'dim_company',
            required_columns=['ticker', 'name', 'exchange_code']
        )

        result = companies_df.groupBy('exchange_code').agg(
            F.count('ticker').alias('company_count')
        ).orderBy(F.desc('company_count'))

        data = result.collect()

        print(f"\n✓ Company Count by Exchange ({len(data)} exchanges)")
        print(f"{'Exchange':<15} {'Companies':>12}")
        print("-" * 30)
        for row in data[:10]:
            print(f"{row.exchange_code:<15} {row.company_count:>12,}")


# ============================================================
# MEASURE FORMATTING TESTS
# ============================================================

class TestMeasureFormatting:
    """Test applying formatting to measure results."""

    def test_currency_formatting(self, session, sample_tickers, date_range):
        """Test currency formatted measures."""
        start_date, end_date = date_range

        prices_df = session.get_table('company', 'fact_prices')

        result = prices_df.filter(
            (F.col('ticker').isin(sample_tickers[:5])) &
            (F.col('trade_date').between(start_date, end_date))
        ).groupBy('ticker').agg(
            F.avg('close').alias('avg_close'),
            F.min('close').alias('min_close'),
            F.max('close').alias('max_close')
        ).orderBy('ticker')

        data = result.collect()

        print(f"\n✓ Currency Formatted Measures")
        print(f"{'Ticker':<10} {'Avg':>12} {'Min':>12} {'Max':>12}")
        print("-" * 50)
        for row in data:
            # Apply $#,##0.00 formatting
            print(f"{row.ticker:<10} ${row.avg_close:>11,.2f} ${row.min_close:>11,.2f} ${row.max_close:>11,.2f}")

    def test_percentage_formatting(self, session, sample_tickers, date_range):
        """Test percentage formatted measures."""
        start_date, end_date = date_range

        prices_df = session.get_table('company', 'fact_prices')

        # Calculate daily returns
        from pyspark.sql.window import Window

        window_spec = Window.partitionBy('ticker').orderBy('trade_date')

        result = prices_df.filter(
            (F.col('ticker').isin(sample_tickers[:5])) &
            (F.col('trade_date').between(start_date, end_date))
        ).withColumn(
            'prev_close', F.lag('close').over(window_spec)
        ).withColumn(
            'daily_return', ((F.col('close') - F.col('prev_close')) / F.col('prev_close') * 100)
        ).groupBy('ticker').agg(
            F.avg('daily_return').alias('avg_daily_return'),
            F.stddev('daily_return').alias('return_volatility')
        ).orderBy('ticker')

        data = result.collect()

        print(f"\n✓ Percentage Formatted Measures")
        print(f"{'Ticker':<10} {'Avg Daily Return':>18} {'Volatility':>12}")
        print("-" * 43)
        for row in data:
            if row.avg_daily_return is not None:
                # Apply #,##0.00% formatting
                print(f"{row.ticker:<10} {row.avg_daily_return:>17,.2f}% {row.return_volatility:>11,.2f}%")


# ============================================================
# MAIN - Run as standalone script
# ============================================================

if __name__ == "__main__":
    """Run tests standalone for quick verification."""
    import sys

    print("=" * 70)
    print("MEASURES WITH SPARK - STANDALONE TEST RUN")
    print("=" * 70)

    # Initialize
    ctx = RepoContext.from_repo_root()
    # Note: 'company' model is deprecated but kept for backward compatibility
    session = UniversalSession(
        connection=ctx.connection,
        storage_cfg=ctx.storage,
        repo_root=REPO_ROOT,
        models=['core', 'company', 'equity', 'corporate', 'forecast']
    )
    registry = ModelRegistry(str(REPO_ROOT / "configs" / "models"))

    sample_tickers = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
        "META", "TSLA", "BRK.B", "JPM", "V",
        "JNJ", "WMT", "PG", "MA", "HD",
        "DIS", "BAC", "ADBE", "NFLX", "CRM"
    ]

    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    date_range = (start_date.isoformat(), end_date.isoformat())

    print(f"\nDate Range: {start_date} to {end_date}")
    print(f"Sample Tickers: {len(sample_tickers)}")

    # Run test instances
    try:
        # Measure loading
        test_loading = TestMeasureLoading()
        test_loading.test_load_company_measures(registry)
        test_loading.test_load_equity_measures(registry)
        test_loading.test_load_forecast_measures(registry)

        # Company measures
        test_company = TestCompanyMeasures()
        test_company.test_avg_close_price_by_ticker(session, sample_tickers, date_range)
        test_company.test_total_volume_by_ticker(session, sample_tickers, date_range)
        test_company.test_market_cap_proxy(session, sample_tickers, date_range)
        test_company.test_price_volatility(session, sample_tickers, date_range)
        test_company.test_daily_range_measure(session, sample_tickers, date_range)

        # Time-based
        test_time = TestTimeBasedMeasures()
        test_time.test_monthly_avg_price(session, sample_tickers, date_range)
        test_time.test_weekly_measures(session, sample_tickers, date_range)

        # Cross-model
        test_cross = TestCrossModelMeasures()
        test_cross.test_prices_with_calendar_measures(session, sample_tickers, date_range)
        test_cross.test_company_count_by_exchange(session)

        # Formatting
        test_format = TestMeasureFormatting()
        test_format.test_currency_formatting(session, sample_tickers, date_range)
        test_format.test_percentage_formatting(session, sample_tickers, date_range)

        print("\n" + "=" * 70)
        print("✓ ALL TESTS PASSED")
        print("=" * 70)

    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        ctx.spark.stop()
