"""
Connection layer abstraction for data access.

Provides interface for different backend connections (Spark, DuckDB, graph DB, etc.)
with Delta Lake support for both backends.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from pathlib import Path
import pandas as pd
import logging

from de_funk.config.constants import DEFAULT_DUCKDB_PATH
from de_funk.utils.repo import get_repo_root

logger = logging.getLogger(__name__)


class DataConnection(ABC):
    """
    Abstract base class for data connections.

    Future implementations:
    - SparkConnection (current)
    - DuckDBConnection
    - GraphDBConnection (Neo4j, etc.)
    - ArrowConnection
    """

    @abstractmethod
    def read_table(self, path: str, format: str = "parquet") -> Any:
        """
        Read a table from storage.

        Args:
            path: Path to table
            format: Format (parquet, delta, csv, etc.)

        Returns:
            DataFrame-like object (specific to connection type)
        """
        pass

    @abstractmethod
    def apply_filters(self, df: Any, filters: Dict[str, Any]) -> Any:
        """
        Apply filters to a dataframe.

        Args:
            df: DataFrame-like object
            filters: Dict of column -> value/condition

        Returns:
            Filtered dataframe
        """
        pass

    @abstractmethod
    def to_pandas(self, df: Any) -> pd.DataFrame:
        """
        Convert to Pandas DataFrame.

        Args:
            df: DataFrame-like object

        Returns:
            Pandas DataFrame
        """
        pass

    @abstractmethod
    def count(self, df: Any) -> int:
        """Get row count."""
        pass

    @abstractmethod
    def cache(self, df: Any) -> Any:
        """Cache dataframe in memory."""
        pass

    @abstractmethod
    def uncache(self, df: Any):
        """Remove from cache."""
        pass

    @abstractmethod
    def stop(self):
        """Close connection and cleanup resources."""
        pass


class SparkConnection(DataConnection):
    """
    Spark-based data connection with Delta Lake support.

    Supports both Parquet and Delta Lake formats for distributed processing.
    Requires delta-spark package for Delta Lake operations.
    """

    def __init__(self, spark_session):
        """
        Initialize Spark connection.

        Args:
            spark_session: PySpark SparkSession
                          For Delta support, session should include Delta Lake extensions:
                          .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
                          .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        """
        self.spark = spark_session
        self._cached_dfs = []

        # Check if Delta is available
        try:
            from delta import DeltaTable
            self.delta_available = True
        except ImportError:
            self.delta_available = False
            logger.warning("delta-spark not installed. Delta Lake operations will not be available.")

    def read_table(self, path: str, format: str = "parquet", version: Optional[int] = None, timestamp: Optional[str] = None):
        """
        Read table using Spark with optional Delta Lake time travel.

        Args:
            path: Path to table or catalog table name
            format: Format ('parquet', 'delta', or any Spark-supported format)
            version: For Delta tables, specific version to read (time travel)
            timestamp: For Delta tables, timestamp to read (time travel)

        Returns:
            Spark DataFrame

        Example:
            # Read Delta table
            df = conn.read_table('/path/to/delta', format='delta')

            # Read with time travel (version)
            df = conn.read_table('/path/to/delta', format='delta', version=5)

            # Read with time travel (timestamp)
            df = conn.read_table('/path/to/delta', format='delta',
                                 timestamp='2024-01-15 10:00:00')
        """
        # Start with base reader
        reader = self.spark.read.format(format)

        # Add time travel options for Delta
        if format == "delta":
            if version is not None:
                reader = reader.option("versionAsOf", version)
            elif timestamp is not None:
                reader = reader.option("timestampAsOf", timestamp)

        return reader.load(path)

    def write_delta_table(
        self,
        df,  # Spark DataFrame
        path: str,
        mode: str = "overwrite",
        partition_by: Optional[List[str]] = None,
        **options
    ):
        """
        Write Spark DataFrame to Delta Lake table.

        Args:
            df: Spark DataFrame to write
            path: Path to Delta table
            mode: Write mode ('overwrite', 'append', 'merge')
            partition_by: Columns to partition by
            **options: Additional write options

        Note: For 'merge' mode, use merge_delta_table() instead which provides
              more control over merge logic.

        Example:
            # Overwrite
            conn.write_delta_table(df, '/path/to/delta', mode='overwrite')

            # Append with partitioning
            conn.write_delta_table(df, '/path/to/delta', mode='append',
                                  partition_by=['year', 'month'])
        """
        if not self.delta_available:
            raise ImportError(
                "Delta operations require delta-spark package. "
                "Install with: pip install delta-spark"
            )

        if mode == "merge":
            raise ValueError(
                "For merge operations, use merge_delta_table() method instead "
                "which provides more control over merge logic."
            )

        # Build writer
        writer = df.write.format("delta").mode(mode)

        # Add partitioning
        if partition_by:
            writer = writer.partitionBy(*partition_by)

        # Add any additional options
        for key, value in options.items():
            writer = writer.option(key, value)

        # Write
        writer.save(path)
        logger.info(f"Wrote DataFrame to Delta table at {path} (mode={mode})")

    def merge_delta_table(
        self,
        source_df,  # Spark DataFrame
        target_path: str,
        merge_condition: str,
        update_set: Optional[Dict[str, str]] = None,
        insert_values: Optional[Dict[str, str]] = None
    ):
        """
        Merge (upsert) data into Delta table using Spark's Delta Lake API.

        Args:
            source_df: Spark DataFrame with source data
            target_path: Path to target Delta table
            merge_condition: SQL condition for matching (e.g., "target.id = source.id")
            update_set: Dict of column updates for matched rows (default: update all)
            insert_values: Dict of column values for not matched rows (default: insert all)

        Example:
            # Basic merge (update all, insert all)
            conn.merge_delta_table(
                source_df,
                '/path/to/delta',
                merge_condition="target.ticker = source.ticker AND target.trade_date = source.trade_date"
            )

            # Custom update/insert logic
            conn.merge_delta_table(
                source_df,
                '/path/to/delta',
                merge_condition="target.id = source.id",
                update_set={"value": "source.value", "updated_at": "source.updated_at"},
                insert_values={"*": "*"}  # Insert all columns
            )
        """
        if not self.delta_available:
            raise ImportError("Merge requires delta-spark package")

        from delta.tables import DeltaTable

        # Load target Delta table
        target_table = DeltaTable.forPath(self.spark, target_path)

        # Build merge operation
        merge = target_table.alias("target").merge(
            source_df.alias("source"),
            merge_condition
        )

        # When matched - update
        if update_set:
            merge = merge.whenMatchedUpdate(set=update_set)
        else:
            merge = merge.whenMatchedUpdateAll()

        # When not matched - insert
        if insert_values:
            merge = merge.whenNotMatchedInsert(values=insert_values)
        else:
            merge = merge.whenNotMatchedInsertAll()

        # Execute merge
        merge.execute()
        logger.info(f"Merged data into Delta table at {target_path}")

    def optimize_delta_table(self, path: str, zorder_by: Optional[List[str]] = None):
        """
        Optimize Delta table (compact files, optionally z-order).

        Args:
            path: Path to Delta table
            zorder_by: Columns to z-order by (for better data skipping)

        Example:
            # Basic optimization
            conn.optimize_delta_table('/path/to/delta')

            # With z-ordering
            conn.optimize_delta_table('/path/to/delta', zorder_by=['ticker', 'trade_date'])
        """
        if not self.delta_available:
            raise ImportError("Optimize requires delta-spark package")

        from delta.tables import DeltaTable

        # Load Delta table
        dt = DeltaTable.forPath(self.spark, path)

        # Optimize (compact)
        if zorder_by:
            dt.optimize().executeZOrderBy(zorder_by)
            logger.info(f"Optimized and z-ordered Delta table at {path} by {zorder_by}")
        else:
            dt.optimize().executeCompaction()
            logger.info(f"Optimized Delta table at {path}")

    def vacuum_delta_table(self, path: str, retention_hours: int = 168):
        """
        Vacuum Delta table (remove old files).

        Args:
            path: Path to Delta table
            retention_hours: Retention period in hours (default: 168 = 7 days)

        Warning: Vacuuming permanently deletes old data files and disables
                 time travel to versions older than retention period!

        Example:
            # Vacuum with default 7-day retention
            conn.vacuum_delta_table('/path/to/delta')

            # Custom retention
            conn.vacuum_delta_table('/path/to/delta', retention_hours=24)
        """
        if not self.delta_available:
            raise ImportError("Vacuum requires delta-spark package")

        from delta.tables import DeltaTable

        # Load Delta table
        dt = DeltaTable.forPath(self.spark, path)

        # Vacuum
        dt.vacuum(retention_hours / 24.0)  # Spark uses days
        logger.info(f"Vacuumed Delta table at {path} (retention={retention_hours}h)")

    def get_delta_table_history(self, path: str, limit: Optional[int] = None) -> pd.DataFrame:
        """
        Get version history of Delta table.

        Args:
            path: Path to Delta table
            limit: Optional limit on number of versions to return

        Returns:
            Pandas DataFrame with history (version, timestamp, operation, etc.)

        Example:
            history = conn.get_delta_table_history('/path/to/delta')
            print(history[['version', 'timestamp', 'operation']])
        """
        if not self.delta_available:
            raise ImportError("Delta history requires delta-spark package")

        from delta.tables import DeltaTable

        # Load Delta table
        dt = DeltaTable.forPath(self.spark, path)

        # Get history
        history_df = dt.history(limit if limit else 1000)

        # Convert to Pandas
        return history_df.toPandas()

    def _is_delta_table(self, path: str) -> bool:
        """
        Check if path points to a Delta Lake table.

        Args:
            path: Path to check

        Returns:
            True if Delta table, False otherwise
        """
        path_obj = Path(path)
        if not path_obj.exists():
            return False

        # Delta tables have _delta_log directory
        return (path_obj / "_delta_log").exists()

    def apply_filters(self, df, filters: Dict[str, Any]):
        """Apply filters using Spark SQL."""
        from pyspark.sql import functions as F

        for column, value in filters.items():
            if isinstance(value, dict):
                # Handle date range
                if 'start' in value and 'end' in value:
                    start = value['start']
                    end = value['end']

                    # Convert datetime to string if needed
                    if hasattr(start, 'strftime'):
                        start = start.strftime('%Y-%m-%d')
                    if hasattr(end, 'strftime'):
                        end = end.strftime('%Y-%m-%d')

                    df = df.filter((F.col(column) >= start) & (F.col(column) <= end))

            elif isinstance(value, list):
                # Handle list of values
                if value:  # Only filter if list is not empty
                    df = df.filter(F.col(column).isin(value))

            else:
                # Handle single value
                df = df.filter(F.col(column) == value)

        return df

    def to_pandas(self, df) -> pd.DataFrame:
        """
        Convert Spark DataFrame to pandas.

        Args:
            df: Spark DataFrame, pandas DataFrame, or QueryResult

        Returns:
            Pandas DataFrame
        """
        # Check if already pandas DataFrame
        if isinstance(df, pd.DataFrame):
            return df

        # Handle QueryResult wrapper (from measure execution)
        if hasattr(df, 'data'):
            df = df.data
            # Check if data is already pandas
            if isinstance(df, pd.DataFrame):
                return df

        # Convert Spark DataFrame to pandas
        return df.toPandas()

    def count(self, df) -> int:
        """Get row count."""
        return df.count()

    def cache(self, df):
        """Cache Spark DataFrame."""
        df.cache()
        self._cached_dfs.append(df)
        return df

    def uncache(self, df):
        """Uncache Spark DataFrame."""
        df.unpersist()
        if df in self._cached_dfs:
            self._cached_dfs.remove(df)

    def stop(self):
        """Stop Spark session and cleanup."""
        # Unpersist all cached dataframes
        for df in self._cached_dfs:
            df.unpersist()
        self._cached_dfs.clear()

        # Stop Spark session
        if self.spark:
            self.spark.stop()


class ConnectionFactory:
    """
    Factory for creating data connections.

    Supports different connection types based on configuration.
    """

    @staticmethod
    def create(connection_type: str = "spark", **kwargs) -> DataConnection:
        """
        Create a data connection.

        Args:
            connection_type: Type of connection ('spark', 'duckdb', 'graph', etc.)
            **kwargs: Connection-specific arguments

        Returns:
            DataConnection instance

        Raises:
            ValueError: If connection type is not supported
        """
        if connection_type == "spark":
            spark_session = kwargs.get('spark_session')
            if not spark_session:
                raise ValueError("spark_session required for Spark connection")
            return SparkConnection(spark_session)

        elif connection_type == "duckdb":
            try:
                from .duckdb_connection import DuckDBConnection
                return DuckDBConnection(**kwargs)
            except ImportError:
                raise ValueError(
                    "DuckDB connection requires 'duckdb' package. "
                    "Install it with: pip install duckdb"
                )

        # Future implementations:
        # elif connection_type == "graph":
        #     return GraphDBConnection(**kwargs)

        else:
            raise ValueError(f"Unsupported connection type: {connection_type}")


# Convenience functions for getting connections
def get_spark_connection(spark_session) -> SparkConnection:
    """
    Get a Spark connection.

    Args:
        spark_session: PySpark SparkSession

    Returns:
        SparkConnection instance
    """
    return ConnectionFactory.create("spark", spark_session=spark_session)


def get_duckdb_connection(db_path: str = None, auto_init_views: bool = True, **kwargs):
    """
    Get a DuckDB connection with sensible defaults.

    Args:
        db_path: Path to DuckDB database (default: storage/duckdb/analytics.db)
        auto_init_views: Whether to auto-initialize v2.0 model views (default: True)
        **kwargs: Additional arguments passed to DuckDBConnection

    Returns:
        DuckDBConnection instance

    Example:
        # Production connection with auto-initialized views
        conn = get_duckdb_connection()

        # In-memory for tests
        conn = get_duckdb_connection(db_path=":memory:")

        # Custom path
        conn = get_duckdb_connection(db_path="path/to/custom.db")
    """
    if db_path is None:
        # Default to analytics database using config constant
        repo_root = get_repo_root()
        db_path = str(repo_root / DEFAULT_DUCKDB_PATH)

    return ConnectionFactory.create("duckdb", db_path=db_path, auto_init_views=auto_init_views, **kwargs)
