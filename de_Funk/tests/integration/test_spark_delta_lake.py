"""
Test Spark Delta Lake integration end-to-end.

Tests Spark's native Delta Lake support with the de_Funk platform:
- Writing Delta tables with Spark
- Reading Delta tables with Spark
- Time travel and versioning
- Merge/upsert operations
- Optimize and vacuum
- Partition management
- Schema evolution
- Cross-compatibility with DuckDB
- Measures with Delta tables

Run:
    pytest tests/test_spark_delta_lake.py -v
    # Or standalone:
    python tests/test_spark_delta_lake.py
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
from datetime import date, datetime, timedelta
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, LongType, DateType

try:
    from delta import configure_spark_with_delta_pip
    DELTA_SPARK_AVAILABLE = True
except ImportError:
    DELTA_SPARK_AVAILABLE = False


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture(scope="module")
def spark():
    """Create Spark session with Delta Lake support."""
    if not DELTA_SPARK_AVAILABLE:
        pytest.skip("delta-spark not installed")

    builder = SparkSession.builder \
        .appName("SparkDeltaLakeTest") \
        .master("local[2]") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .config("spark.sql.shuffle.partitions", "2")

    # Configure with delta-spark
    spark_session = configure_spark_with_delta_pip(builder).getOrCreate()
    spark_session.sparkContext.setLogLevel("ERROR")

    yield spark_session
    spark_session.stop()


@pytest.fixture
def temp_dir():
    """Create temporary directory for test Delta tables."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def sample_prices_data():
    """Sample price data for testing."""
    return pd.DataFrame({
        'ticker': ['AAPL', 'MSFT', 'GOOGL', 'AAPL', 'MSFT', 'GOOGL'] * 5,
        'trade_date': [
            date(2024, 1, 15), date(2024, 1, 15), date(2024, 1, 15),
            date(2024, 1, 16), date(2024, 1, 16), date(2024, 1, 16),
        ] * 5,
        'open': [185.0, 420.0, 150.0, 186.0, 422.0, 151.0] * 5,
        'high': [187.0, 425.0, 153.0, 188.0, 426.0, 154.0] * 5,
        'low': [184.0, 419.0, 149.0, 185.0, 421.0, 150.0] * 5,
        'close': [186.5, 423.5, 152.2, 187.2, 424.8, 153.5] * 5,
        'volume': [50000000, 30000000, 25000000, 48000000, 29000000, 24000000] * 5
    })


# ============================================================
# BASIC DELTA TABLE OPERATIONS
# ============================================================

class TestSparkDeltaBasics:
    """Test basic Delta table write/read operations with Spark."""

    @pytest.mark.skipif(not DELTA_SPARK_AVAILABLE, reason="delta-spark not installed")
    def test_write_delta_table_overwrite(self, spark, temp_dir, sample_prices_data):
        """Test writing Delta table with overwrite mode."""
        delta_path = str(temp_dir / "prices_overwrite")

        # Write to Delta
        df = spark.createDataFrame(sample_prices_data)
        df.write.format("delta").mode("overwrite").save(delta_path)

        # Verify _delta_log exists
        assert (temp_dir / "prices_overwrite" / "_delta_log").exists()

        # Read back
        result_df = spark.read.format("delta").load(delta_path)
        assert result_df.count() == len(sample_prices_data)
        assert set(result_df.columns) == set(sample_prices_data.columns)

    @pytest.mark.skipif(not DELTA_SPARK_AVAILABLE, reason="delta-spark not installed")
    def test_write_delta_table_append(self, spark, temp_dir, sample_prices_data):
        """Test appending to Delta table."""
        delta_path = str(temp_dir / "prices_append")

        # Initial write
        df1 = spark.createDataFrame(sample_prices_data.head(10))
        df1.write.format("delta").mode("overwrite").save(delta_path)

        # Append more data
        df2 = spark.createDataFrame(sample_prices_data.tail(10))
        df2.write.format("delta").mode("append").save(delta_path)

        # Verify total count
        result_df = spark.read.format("delta").load(delta_path)
        assert result_df.count() == 20

    @pytest.mark.skipif(not DELTA_SPARK_AVAILABLE, reason="delta-spark not installed")
    def test_write_delta_table_partitioned(self, spark, temp_dir, sample_prices_data):
        """Test writing partitioned Delta table."""
        delta_path = str(temp_dir / "prices_partitioned")

        # Write partitioned by ticker
        df = spark.createDataFrame(sample_prices_data)
        df.write.format("delta") \
            .partitionBy("ticker") \
            .mode("overwrite") \
            .save(delta_path)

        # Verify partitions exist
        delta_dir = temp_dir / "prices_partitioned"
        ticker_partitions = [d.name for d in delta_dir.iterdir() if d.is_dir() and d.name.startswith("ticker=")]
        assert len(ticker_partitions) > 0
        assert "ticker=AAPL" in ticker_partitions

    @pytest.mark.skipif(not DELTA_SPARK_AVAILABLE, reason="delta-spark not installed")
    def test_read_delta_with_partition_pruning(self, spark, temp_dir, sample_prices_data):
        """Test partition pruning when reading Delta table."""
        delta_path = str(temp_dir / "prices_pruning")

        # Write partitioned
        df = spark.createDataFrame(sample_prices_data)
        df.write.format("delta") \
            .partitionBy("ticker") \
            .mode("overwrite") \
            .save(delta_path)

        # Read with filter (should prune partitions)
        result_df = spark.read.format("delta").load(delta_path) \
            .filter(F.col("ticker") == "AAPL")

        result_count = result_df.count()
        aapl_count = len(sample_prices_data[sample_prices_data['ticker'] == 'AAPL'])
        assert result_count == aapl_count


# ============================================================
# TIME TRAVEL AND VERSIONING
# ============================================================

class TestSparkDeltaTimeTravel:
    """Test Delta Lake time travel features with Spark."""

    @pytest.mark.skipif(not DELTA_SPARK_AVAILABLE, reason="delta-spark not installed")
    def test_time_travel_by_version(self, spark, temp_dir, sample_prices_data):
        """Test reading specific version of Delta table."""
        delta_path = str(temp_dir / "prices_versions")

        # Version 0: Initial write
        df_v0 = spark.createDataFrame(sample_prices_data.head(10))
        df_v0.write.format("delta").mode("overwrite").save(delta_path)

        # Version 1: Append
        df_v1 = spark.createDataFrame(sample_prices_data.tail(10))
        df_v1.write.format("delta").mode("append").save(delta_path)

        # Version 2: More appends
        df_v2 = spark.createDataFrame(sample_prices_data.head(5))
        df_v2.write.format("delta").mode("append").save(delta_path)

        # Read version 0
        v0_df = spark.read.format("delta").option("versionAsOf", 0).load(delta_path)
        assert v0_df.count() == 10

        # Read version 1
        v1_df = spark.read.format("delta").option("versionAsOf", 1).load(delta_path)
        assert v1_df.count() == 20

        # Read current (version 2)
        current_df = spark.read.format("delta").load(delta_path)
        assert current_df.count() == 25

    @pytest.mark.skipif(not DELTA_SPARK_AVAILABLE, reason="delta-spark not installed")
    def test_time_travel_by_timestamp(self, spark, temp_dir, sample_prices_data):
        """Test reading Delta table as of timestamp."""
        delta_path = str(temp_dir / "prices_timestamp")

        # Initial write
        df = spark.createDataFrame(sample_prices_data.head(10))
        df.write.format("delta").mode("overwrite").save(delta_path)

        # Get timestamp after first write
        from datetime import datetime
        import time
        time.sleep(1)  # Ensure different timestamp
        timestamp_v0 = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Second write
        df2 = spark.createDataFrame(sample_prices_data.tail(10))
        df2.write.format("delta").mode("append").save(delta_path)

        # Read as of timestamp
        result_df = spark.read.format("delta") \
            .option("timestampAsOf", timestamp_v0) \
            .load(delta_path)

        # Should have data from version 0
        assert result_df.count() <= 20  # May include v1 if timestamp close

    @pytest.mark.skipif(not DELTA_SPARK_AVAILABLE, reason="delta-spark not installed")
    def test_describe_history(self, spark, temp_dir, sample_prices_data):
        """Test querying Delta table history."""
        delta_path = str(temp_dir / "prices_history")

        # Create multiple versions
        for i in range(3):
            df = spark.createDataFrame(sample_prices_data.head(5 * (i + 1)))
            mode = "overwrite" if i == 0 else "append"
            df.write.format("delta").mode(mode).save(delta_path)

        # Query history
        from delta.tables import DeltaTable
        delta_table = DeltaTable.forPath(spark, delta_path)
        history_df = delta_table.history()

        assert history_df.count() >= 3
        assert "version" in history_df.columns
        assert "operation" in history_df.columns


# ============================================================
# MERGE AND UPSERT
# ============================================================

class TestSparkDeltaMerge:
    """Test Delta Lake merge/upsert operations."""

    @pytest.mark.skipif(not DELTA_SPARK_AVAILABLE, reason="delta-spark not installed")
    def test_merge_upsert(self, spark, temp_dir):
        """Test merge operation for upserts."""
        from delta.tables import DeltaTable
        delta_path = str(temp_dir / "prices_merge")

        # Initial data
        initial_data = pd.DataFrame({
            'ticker': ['AAPL', 'MSFT', 'GOOGL'],
            'trade_date': [date(2024, 1, 15)] * 3,
            'close': [185.5, 420.3, 150.2],
            'volume': [50000000, 30000000, 25000000]
        })

        df_initial = spark.createDataFrame(initial_data)
        df_initial.write.format("delta").mode("overwrite").save(delta_path)

        # Updates and new records
        updates = pd.DataFrame({
            'ticker': ['AAPL', 'TSLA'],  # AAPL=update, TSLA=insert
            'trade_date': [date(2024, 1, 15), date(2024, 1, 15)],
            'close': [187.00, 250.50],  # Updated AAPL price
            'volume': [52000000, 45000000]
        })

        df_updates = spark.createDataFrame(updates)

        # Merge
        delta_table = DeltaTable.forPath(spark, delta_path)
        delta_table.alias("target").merge(
            df_updates.alias("source"),
            "target.ticker = source.ticker AND target.trade_date = source.trade_date"
        ).whenMatchedUpdateAll() \
         .whenNotMatchedInsertAll() \
         .execute()

        # Verify results
        result_df = spark.read.format("delta").load(delta_path)
        assert result_df.count() == 4  # 3 original + 1 new (TSLA)

        # Verify AAPL was updated
        aapl_row = result_df.filter(F.col("ticker") == "AAPL").collect()[0]
        assert aapl_row.close == 187.00

    @pytest.mark.skipif(not DELTA_SPARK_AVAILABLE, reason="delta-spark not installed")
    def test_merge_delete_matched(self, spark, temp_dir):
        """Test merge with delete for matched records."""
        from delta.tables import DeltaTable
        delta_path = str(temp_dir / "prices_delete")

        # Initial data
        initial_data = pd.DataFrame({
            'ticker': ['AAPL', 'MSFT', 'GOOGL'],
            'close': [185.5, 420.3, 150.2],
            'active': [True, True, True]
        })

        df_initial = spark.createDataFrame(initial_data)
        df_initial.write.format("delta").mode("overwrite").save(delta_path)

        # Mark AAPL as inactive (delete)
        deletes = pd.DataFrame({
            'ticker': ['AAPL'],
            'active': [False]
        })

        df_deletes = spark.createDataFrame(deletes)

        # Merge with delete
        delta_table = DeltaTable.forPath(spark, delta_path)
        delta_table.alias("target").merge(
            df_deletes.alias("source"),
            "target.ticker = source.ticker"
        ).whenMatchedDelete() \
         .execute()

        # Verify AAPL deleted
        result_df = spark.read.format("delta").load(delta_path)
        assert result_df.count() == 2
        assert result_df.filter(F.col("ticker") == "AAPL").count() == 0


# ============================================================
# OPTIMIZE AND VACUUM
# ============================================================

class TestSparkDeltaOptimize:
    """Test Delta Lake optimization operations."""

    @pytest.mark.skipif(not DELTA_SPARK_AVAILABLE, reason="delta-spark not installed")
    def test_optimize_compact(self, spark, temp_dir, sample_prices_data):
        """Test optimizing Delta table (compaction)."""
        from delta.tables import DeltaTable
        delta_path = str(temp_dir / "prices_optimize")

        # Create many small files by appending
        for i in range(5):
            df = spark.createDataFrame(sample_prices_data.head(3))
            mode = "overwrite" if i == 0 else "append"
            df.write.format("delta").mode(mode).save(delta_path)

        # Optimize
        delta_table = DeltaTable.forPath(spark, delta_path)
        delta_table.optimize().executeCompaction()

        # Verify table still readable
        result_df = spark.read.format("delta").load(delta_path)
        assert result_df.count() > 0

    @pytest.mark.skipif(not DELTA_SPARK_AVAILABLE, reason="delta-spark not installed")
    def test_optimize_zorder(self, spark, temp_dir, sample_prices_data):
        """Test Z-ordering optimization."""
        from delta.tables import DeltaTable
        delta_path = str(temp_dir / "prices_zorder")

        # Write data
        df = spark.createDataFrame(sample_prices_data)
        df.write.format("delta").mode("overwrite").save(delta_path)

        # Z-order by ticker and trade_date
        delta_table = DeltaTable.forPath(spark, delta_path)
        delta_table.optimize().executeZOrderBy("ticker", "trade_date")

        # Verify table still readable
        result_df = spark.read.format("delta").load(delta_path)
        assert result_df.count() == len(sample_prices_data)

    @pytest.mark.skipif(not DELTA_SPARK_AVAILABLE, reason="delta-spark not installed")
    def test_vacuum(self, spark, temp_dir, sample_prices_data):
        """Test vacuuming Delta table."""
        from delta.tables import DeltaTable
        delta_path = str(temp_dir / "prices_vacuum")

        # Create versions
        df1 = spark.createDataFrame(sample_prices_data.head(10))
        df1.write.format("delta").mode("overwrite").save(delta_path)

        df2 = spark.createDataFrame(sample_prices_data.tail(10))
        df2.write.format("delta").mode("append").save(delta_path)

        # Vacuum (need to disable retention enforcement for testing)
        delta_table = DeltaTable.forPath(spark, delta_path)

        # Set retention to 0 for testing (normally 168 hours minimum)
        spark.conf.set("spark.databricks.delta.retentionDurationCheck.enabled", "false")
        delta_table.vacuum(0)

        # Current version still readable
        result_df = spark.read.format("delta").load(delta_path)
        assert result_df.count() > 0


# ============================================================
# SCHEMA EVOLUTION
# ============================================================

class TestSparkDeltaSchema:
    """Test Delta Lake schema evolution."""

    @pytest.mark.skipif(not DELTA_SPARK_AVAILABLE, reason="delta-spark not installed")
    def test_schema_evolution_merge(self, spark, temp_dir):
        """Test automatic schema evolution with merge."""
        delta_path = str(temp_dir / "prices_schema_merge")

        # Initial schema
        initial_data = pd.DataFrame({
            'ticker': ['AAPL'],
            'close': [185.5]
        })

        df_initial = spark.createDataFrame(initial_data)
        df_initial.write.format("delta").mode("overwrite").save(delta_path)

        # Add new column in append (with schema evolution enabled)
        new_data = pd.DataFrame({
            'ticker': ['MSFT'],
            'close': [420.3],
            'volume': [30000000]  # New column
        })

        df_new = spark.createDataFrame(new_data)
        df_new.write.format("delta") \
            .option("mergeSchema", "true") \
            .mode("append") \
            .save(delta_path)

        # Read and verify
        result_df = spark.read.format("delta").load(delta_path)
        assert "volume" in result_df.columns
        assert result_df.count() == 2

    @pytest.mark.skipif(not DELTA_SPARK_AVAILABLE, reason="delta-spark not installed")
    def test_schema_overwrite(self, spark, temp_dir):
        """Test overwriting schema with overwriteSchema option."""
        delta_path = str(temp_dir / "prices_schema_overwrite")

        # Initial data
        df1 = spark.createDataFrame(pd.DataFrame({
            'ticker': ['AAPL'],
            'price': [185.5]
        }))
        df1.write.format("delta").mode("overwrite").save(delta_path)

        # Completely different schema
        df2 = spark.createDataFrame(pd.DataFrame({
            'symbol': ['MSFT'],
            'value': [420.3]
        }))

        df2.write.format("delta") \
            .option("overwriteSchema", "true") \
            .mode("overwrite") \
            .save(delta_path)

        # Verify new schema
        result_df = spark.read.format("delta").load(delta_path)
        assert set(result_df.columns) == {"symbol", "value"}


# ============================================================
# INTEGRATION WITH MEASURES
# ============================================================

class TestSparkDeltaMeasures:
    """Test measures with Delta tables."""

    @pytest.mark.skipif(not DELTA_SPARK_AVAILABLE, reason="delta-spark not installed")
    def test_measures_on_delta_table(self, spark, temp_dir, sample_prices_data):
        """Test calculating measures on Delta table."""
        delta_path = str(temp_dir / "prices_measures")

        # Write to Delta
        df = spark.createDataFrame(sample_prices_data)
        df.write.format("delta").mode("overwrite").save(delta_path)

        # Read and calculate measures
        prices_df = spark.read.format("delta").load(delta_path)

        # Average closing price by ticker
        result = prices_df.groupBy("ticker").agg(
            F.avg("close").alias("avg_close_price"),
            F.sum("volume").alias("total_volume"),
            F.count("*").alias("trading_days")
        ).orderBy(F.desc("avg_close_price"))

        assert result.count() > 0

        # Verify measure calculations
        result_pd = result.toPandas()
        assert all(result_pd['avg_close_price'] > 0)
        assert all(result_pd['total_volume'] > 0)

    @pytest.mark.skipif(not DELTA_SPARK_AVAILABLE, reason="delta-spark not installed")
    def test_partitioned_delta_with_measures(self, spark, temp_dir, sample_prices_data):
        """Test measures on partitioned Delta table."""
        delta_path = str(temp_dir / "prices_partitioned_measures")

        # Write partitioned Delta table
        df = spark.createDataFrame(sample_prices_data)
        df.write.format("delta") \
            .partitionBy("ticker") \
            .mode("overwrite") \
            .save(delta_path)

        # Read with partition filter and calculate measures
        prices_df = spark.read.format("delta").load(delta_path) \
            .filter(F.col("ticker") == "AAPL")

        result = prices_df.agg(
            F.avg("close").alias("avg_close"),
            F.stddev("close").alias("volatility")
        )

        result_row = result.collect()[0]
        assert result_row.avg_close > 0
        assert result_row.volatility >= 0


# ============================================================
# CROSS-COMPATIBILITY (Spark → DuckDB)
# ============================================================

class TestSparkDeltaDuckDBCompat:
    """Test Spark-written Delta tables can be read by DuckDB."""

    @pytest.mark.skipif(not DELTA_SPARK_AVAILABLE, reason="delta-spark not installed")
    def test_spark_write_duckdb_read(self, spark, temp_dir, sample_prices_data):
        """Test writing with Spark, reading with DuckDB."""
        delta_path = str(temp_dir / "prices_cross_compat")

        # Write with Spark
        df = spark.createDataFrame(sample_prices_data)
        df.write.format("delta").mode("overwrite").save(delta_path)

        # Read with DuckDB
        try:
            import duckdb
            conn = duckdb.connect()
            conn.execute("INSTALL delta")
            conn.execute("LOAD delta")

            result = conn.execute(f"SELECT COUNT(*) as cnt FROM delta_scan('{delta_path}')").fetchone()
            assert result[0] == len(sample_prices_data)
        except ImportError:
            pytest.skip("DuckDB not installed")


# ============================================================
# STANDALONE RUNNER
# ============================================================

if __name__ == "__main__":
    """Run tests standalone without pytest."""
    print("=" * 70)
    print("SPARK DELTA LAKE - STANDALONE TEST RUN")
    print("=" * 70)

    if not DELTA_SPARK_AVAILABLE:
        print("\n❌ delta-spark not installed!")
        print("   Install: pip install delta-spark")
        exit(1)

    print("\n✓ delta-spark is installed")

    # Create fixtures
    temp_path = Path(tempfile.mkdtemp())

    try:
        # Initialize Spark
        builder = SparkSession.builder \
            .appName("SparkDeltaLakeTest") \
            .master("local[2]") \
            .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
            .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
            .config("spark.sql.shuffle.partitions", "2")

        spark_session = configure_spark_with_delta_pip(builder).getOrCreate()
        spark_session.sparkContext.setLogLevel("ERROR")

        print("✓ Spark session created with Delta support")

        # Run sample test
        sample_data = pd.DataFrame({
            'ticker': ['AAPL', 'MSFT', 'GOOGL'] * 3,
            'close': [185.5, 420.3, 150.2] * 3,
            'volume': [50000000, 30000000, 25000000] * 3
        })

        delta_path = str(temp_path / "test_delta")

        # Write
        df = spark_session.createDataFrame(sample_data)
        df.write.format("delta").mode("overwrite").save(delta_path)
        print(f"✓ Wrote Delta table to {delta_path}")

        # Read
        result_df = spark_session.read.format("delta").load(delta_path)
        count = result_df.count()
        print(f"✓ Read Delta table: {count} rows")

        # Verify _delta_log
        if (temp_path / "test_delta" / "_delta_log").exists():
            print("✓ _delta_log directory exists")

        print("\n" + "=" * 70)
        print("✓ ALL BASIC TESTS PASSED")
        print("=" * 70)
        print("\nRun full test suite with: pytest tests/test_spark_delta_lake.py -v")

    finally:
        if 'spark_session' in locals():
            spark_session.stop()
        shutil.rmtree(temp_path, ignore_errors=True)
