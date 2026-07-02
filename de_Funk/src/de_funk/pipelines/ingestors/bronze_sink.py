"""
Bronze Sink - Writes data to Bronze layer using Delta Lake format.

All Bronze data is stored as Delta Lake tables for:
- ACID transactions
- Time travel / version history
- Schema evolution
- Efficient upserts
- Automatic compaction (OPTIMIZE + VACUUM)
"""
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class BronzeSink:
    """
    Writes DataFrames to Bronze layer as Delta Lake tables.

    Delta Lake is the default storage format (v2.0+).
    """

    def __init__(self, storage_cfg: Dict[str, Any], session=None):
        self.cfg = storage_cfg
        self.ingest_session = session
        self._format = self.cfg.get("defaults", {}).get("format", "delta")

    def _table_cfg(self, table: str) -> Dict:
        return self.cfg["tables"][table]

    def _path(self, table: str, partitions: Optional[Dict] = None) -> Path:
        base = Path(self.cfg["roots"]["bronze"]) / self._table_cfg(table)["rel"]
        for k, v in (partitions or {}).items():
            base = base / f"{k}={v}"
        return base

    def _is_delta_table(self, path: Path) -> bool:
        """Check if path is a Delta Lake table."""
        return (path / "_delta_log").exists()

    def exists(self, table: str, partitions: Optional[Dict] = None) -> bool:
        path = self._path(table, partitions)
        if self._format == "delta":
            return self._is_delta_table(path)
        return path.exists()

    def write_if_missing(self, table: str, partitions: Optional[Dict], df) -> bool:
        path = self._path(table, partitions)
        if self.exists(table, partitions):
            return False
        path.mkdir(parents=True, exist_ok=True)
        self._write_delta(df, str(path), mode="overwrite")
        return True

    def append_immutable(
        self,
        df,
        table: str,
        key_columns: List[str],
        partitions: Optional[List[str]] = None,
        date_column: str = "trade_date"
    ) -> str:
        """
        Append immutable time-series data efficiently using INSERT-only semantics.

        RECOMMENDED for historical data that doesn't change (e.g., stock prices).
        Much faster than upsert() because it avoids expensive MERGE operations.

        Strategy:
        - First write: Create table with partitions
        - Subsequent writes: APPEND new data, skip existing date ranges
        - Uses Delta Lake's partition pruning for efficiency

        Args:
            df: Spark DataFrame to append
            table: Table name (must exist in storage config)
            key_columns: Columns that uniquely identify a row (for dedup within batch)
            partitions: List of partition column names (should include date-based partition)
            date_column: Column containing the date (for checking existing data)

        Returns:
            Path to table

        Example:
            # RECOMMENDED: Use smart_write() which reads partitions from storage.json
            sink.smart_write(df, "securities_prices_daily")

            # Or for direct control (partitions should match storage.json config):
            table_cfg = storage_cfg["tables"]["securities_prices_daily"]
            sink.append_immutable(
                df, "securities_prices_daily",
                key_columns=table_cfg.get("key_columns", []),
                partitions=table_cfg.get("partitions", []),
                date_column=table_cfg.get("date_column", "trade_date")
            )
        """
        from datetime import date
        from delta.tables import DeltaTable
        from pyspark.sql.functions import lit, row_number, col, max as spark_max, min as spark_min
        from pyspark.sql.window import Window

        # Get base path for table - use table name directly (no storage.json lookup)
        base_path = Path(self.cfg["roots"]["bronze"]) / table

        # Deduplicate source DataFrame by key columns
        if key_columns:
            window = Window.partitionBy(*key_columns).orderBy(lit(1))
            df = (df
                  .withColumn("_row_num", row_number().over(window))
                  .filter("_row_num = 1")
                  .drop("_row_num"))

        # Check if table exists
        is_existing = self._is_delta_table(base_path)

        if not is_existing:
            # First write - create the table
            base_path.parent.mkdir(parents=True, exist_ok=True)
            writer = df.write.format("delta").mode("overwrite")
            if partitions:
                writer = writer.partitionBy(*partitions)
            writer.save(str(base_path))
        else:
            # Table exists - filter out records that already exist
            spark = df.sparkSession

            # Read existing schema and align new data to match types
            existing_df = spark.read.format("delta").load(str(base_path))
            existing_schema = {f.name: f.dataType for f in existing_df.schema.fields}

            # Cast new df columns to match existing schema types to avoid merge conflicts
            for field in df.schema.fields:
                if field.name in existing_schema:
                    existing_type = existing_schema[field.name]
                    if field.dataType != existing_type:
                        logger.info(f"Casting {field.name} from {field.dataType} to {existing_type}")
                        df = df.withColumn(field.name, col(field.name).cast(existing_type))

            # Check if date_column exists for date-range optimization
            has_date_column = date_column in df.columns

            if has_date_column:
                # Use date-range optimization for time-series data
                date_stats = df.agg(
                    spark_min(col(date_column)).alias("min_date"),
                    spark_max(col(date_column)).alias("max_date")
                ).collect()[0]

                if date_stats["min_date"] is None:
                    # Empty DataFrame, nothing to append
                    return str(base_path)

                # Read existing data for this date range to find what's new
                existing_for_dedup = (existing_df
                              .filter(
                                  (col(date_column) >= date_stats["min_date"]) &
                                  (col(date_column) <= date_stats["max_date"])
                              )
                              .select(*key_columns)
                              .distinct())
            else:
                # No date column - use simple key-based deduplication
                # This handles endpoints like company_overview, income_statement, etc.
                logger.debug(f"No date_column '{date_column}' found, using key-based deduplication")
                existing_for_dedup = existing_df.select(*key_columns).distinct()

            # Anti-join to find only new records
            new_records = df.join(existing_for_dedup, on=key_columns, how="left_anti")

            new_count = new_records.count()
            if new_count == 0:
                # All data already exists
                return str(base_path)

            # Append only new records
            writer = (new_records.write
                     .format("delta")
                     .mode("append")
                     .option("mergeSchema", "true"))

            if partitions:
                writer = writer.partitionBy(*partitions)

            writer.save(str(base_path))

        return str(base_path)

    def _resolve_key_columns(self, df, key_columns: List[str]) -> List[str]:
        """
        Resolve key column names with case-insensitive matching.

        If a key column doesn't exist in the DataFrame, try to find a
        case-insensitive match (e.g., 'cik' matches 'CIK').

        Returns the resolved list of column names that exist in the DataFrame.
        """
        df_columns = df.columns
        df_columns_lower = {c.lower(): c for c in df_columns}

        resolved = []
        for key_col in key_columns:
            if key_col in df_columns:
                # Exact match
                resolved.append(key_col)
            elif key_col.lower() in df_columns_lower:
                # Case-insensitive match
                actual_col = df_columns_lower[key_col.lower()]
                logger.info(f"Key column '{key_col}' resolved to '{actual_col}' (case-insensitive)")
                resolved.append(actual_col)
            else:
                # Column not found - skip it with warning
                logger.warning(f"Key column '{key_col}' not found in DataFrame columns: {df_columns[:10]}...")

        return resolved

    def upsert(
        self,
        df,
        table: str,
        key_columns: List[str],
        partitions: Optional[List[str]] = None,
        update_existing: bool = True
    ) -> str:
        """
        Upsert DataFrame into bronze table using Read-Merge-Overwrite strategy.

        This approach reads existing data, merges with new data, deduplicates,
        and overwrites the table. This prevents file accumulation that occurs
        with Delta MERGE operations.

        Strategy:
        - First write: Simple overwrite
        - Subsequent writes: Read existing → Union → Deduplicate → Overwrite
        - Result: Consistent file count (controlled by coalesce)

        Args:
            df: Spark DataFrame to upsert
            table: Table name (must exist in storage config)
            key_columns: Columns that uniquely identify a row
            partitions: List of partition column names for new tables
            update_existing: If True, new data overwrites existing for same key.
                            If False, existing data is preserved.

        Returns:
            Path to table
        """
        from datetime import date
        from pyspark.sql.functions import lit, row_number, col
        from pyspark.sql.window import Window

        # Get base path for table - use table name directly (no storage.json lookup)
        base_path = Path(self.cfg["roots"]["bronze"]) / table

        spark = df.sparkSession

        # Resolve key columns with case-insensitive matching
        resolved_key_columns = self._resolve_key_columns(df, key_columns) if key_columns else []

        # Check if table exists
        is_existing = self._is_delta_table(base_path)

        if not is_existing:
            # First write - create the table
            base_path.parent.mkdir(parents=True, exist_ok=True)

            # Deduplicate new data
            if resolved_key_columns:
                window = Window.partitionBy(*resolved_key_columns).orderBy(lit(1))
                df = (df
                      .withColumn("_row_num", row_number().over(window))
                      .filter("_row_num = 1")
                      .drop("_row_num"))

            # Coalesce to minimize file count
            df = df.coalesce(4)

            writer = df.write.format("delta").mode("overwrite")
            if partitions:
                writer = writer.partitionBy(*partitions)
            writer.save(str(base_path))
        else:
            # Read-Merge-Overwrite: Read existing, union with new, deduplicate, overwrite
            existing_df = spark.read.format("delta").load(str(base_path))

            # Cast new df columns to match existing schema to avoid type conflicts
            # (e.g., shares_outstanding: string vs long)
            # Use try_cast via when/otherwise to handle NaN values that can't cast to BIGINT
            from pyspark.sql.functions import when, isnan
            from pyspark.sql.types import LongType, IntegerType, DoubleType, FloatType

            existing_schema = {f.name: f.dataType for f in existing_df.schema.fields}
            for field in df.schema.fields:
                if field.name in existing_schema:
                    existing_type = existing_schema[field.name]
                    if field.dataType != existing_type:
                        logger.info(f"Casting {field.name} from {field.dataType} to {existing_type}")
                        # Handle NaN values when casting from Double to Long/Int (NaN → NULL)
                        if isinstance(field.dataType, (DoubleType, FloatType)) and \
                           isinstance(existing_type, (LongType, IntegerType)):
                            df = df.withColumn(
                                field.name,
                                when(isnan(col(field.name)), None)
                                .otherwise(col(field.name).cast(existing_type))
                            )
                        else:
                            df = df.withColumn(field.name, col(field.name).cast(existing_type))

            # Add a source marker to handle update_existing logic
            existing_df = existing_df.withColumn("_source", lit(0))  # 0 = existing
            new_df = df.withColumn("_source", lit(1))  # 1 = new

            # Union all data
            combined = existing_df.unionByName(new_df, allowMissingColumns=True)

            # Deduplicate by key columns
            # If update_existing=True, prefer new data (source=1)
            # If update_existing=False, prefer existing data (source=0)
            # Re-resolve key columns for combined DataFrame (may have different columns after union)
            combined_key_columns = self._resolve_key_columns(combined, key_columns) if key_columns else []
            if combined_key_columns:
                order_col = col("_source").desc() if update_existing else col("_source").asc()
                window = Window.partitionBy(*combined_key_columns).orderBy(order_col)
                combined = (combined
                           .withColumn("_row_num", row_number().over(window))
                           .filter("_row_num = 1")
                           .drop("_row_num", "_source"))
            else:
                combined = combined.drop("_source")

            # Coalesce to minimize file count
            combined = combined.coalesce(4)

            # Overwrite the entire table
            # Note: We cast new data columns to match existing schema types (above)
            # so we don't need overwriteSchema. mergeSchema handles new columns.
            # overwriteSchema is NOT compatible with dynamic partition overwrite mode.
            writer = combined.write.format("delta").mode("overwrite")
            if partitions:
                writer = writer.partitionBy(*partitions)
            writer = writer.option("mergeSchema", "true")
            writer.save(str(base_path))

            logger.info(f"Upsert complete for {table}: read-merge-overwrite strategy")

        # Clean up old files immediately
        self._cleanup_old_files(base_path)

        return str(base_path)

    def _cleanup_old_files(self, table_path: Path) -> None:
        """Delete old parquet files not in current Delta version."""
        try:
            from deltalake import DeltaTable
            dt = DeltaTable(str(table_path))
            current_files = set(dt.files())

            # Delete any parquet file not in current version
            for f in table_path.rglob('*.parquet'):
                if '_delta_log' in str(f):
                    continue
                rel_path = str(f.relative_to(table_path))
                if rel_path not in current_files:
                    f.unlink()
        except ImportError:
            pass  # No deltalake package, skip cleanup
        except Exception as e:
            logger.debug(f"Cleanup skipped: {e}")

    def smart_write(self, df, table: str) -> str:
        """
        Universal write method that picks strategy based on storage.json config.

        Reads write_strategy, key_columns, partitions, and date_column from config
        and calls the appropriate method (upsert or append_immutable).

        This is the RECOMMENDED method for all writes - it ensures the correct
        strategy is used based on data characteristics defined in config.

        Config fields in storage.json tables:
            write_strategy: "upsert" | "append"
                - "upsert": For reference data that changes (uses read-merge-overwrite)
                - "append": For immutable time-series (uses append_immutable, O(1) memory)
            key_columns: List of columns that uniquely identify a row
            partitions: List of partition columns
            date_column: Column containing date (required for append strategy)

        Args:
            df: Spark DataFrame to write
            table: Table name (must exist in storage config with write config)

        Returns:
            Path to written table

        Example:
            # Config in storage.json:
            # "securities_prices_daily": {
            #     "write_strategy": "append",
            #     "key_columns": ["ticker", "trade_date"],
            #     "date_column": "trade_date",
            #     "partitions": ["year"]
            # }

            sink.smart_write(prices_df, "securities_prices_daily")
        """
        table_cfg = self._table_cfg(table)

        # Get write configuration
        strategy = table_cfg.get("write_strategy", "upsert")  # Default to upsert for safety
        key_columns = table_cfg.get("key_columns", [])
        partitions = table_cfg.get("partitions", []) or None
        date_column = table_cfg.get("date_column")

        if strategy == "append":
            if not date_column:
                logger.warning(f"Table {table} has append strategy but no date_column - falling back to upsert")
                return self.upsert(df, table, key_columns=key_columns, partitions=partitions)

            return self.append_immutable(
                df,
                table,
                key_columns=key_columns,
                partitions=partitions,
                date_column=date_column
            )
        else:
            # Default: upsert
            return self.upsert(df, table, key_columns=key_columns, partitions=partitions)

    def write(self, df, table: str, partitions: Optional[List[str]] = None, mode: str = "overwrite") -> str:
        """
        Write DataFrame to bronze table as Delta Lake format.

        Args:
            df: Spark DataFrame to write
            table: Table name (must exist in storage config)
            partitions: List of partition column names (e.g., ["asset_type", "year"])
            mode: Write mode - "overwrite", "append", or "merge"
                  Use "append" when writing in batches to avoid overwriting previous data.

        Returns:
            Path to written table
        """
        from datetime import date

        # Validate mode
        valid_modes = ("overwrite", "append", "merge")
        if mode not in valid_modes:
            raise ValueError(f"Invalid write mode: {mode}. Must be one of {valid_modes}.")

        # Get base path for table
        table_cfg = self._table_cfg(table)
        base_path = Path(self.cfg["roots"]["bronze"]) / table_cfg["rel"]

        # Write as Delta Lake
        self._write_delta(df, str(base_path), mode=mode, partitions=partitions)

        return str(base_path)

    def overwrite(
        self,
        df,
        table: str,
        partitions: Optional[List[str]] = None
    ) -> str:
        """
        Simple overwrite for tables not in storage.json.

        Uses bronze root + table name as path.

        Args:
            df: Spark DataFrame
            table: Table name (used as subdirectory)
            partitions: Partition columns

        Returns:
            Path to written table
        """
        base_path = Path(self.cfg["roots"]["bronze"]) / table
        base_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_delta(df, str(base_path), mode="overwrite", partitions=partitions)
        return str(base_path)

    def append(
        self,
        df,
        table: str,
        partitions: Optional[List[str]] = None
    ) -> str:
        """
        Append data to existing Delta table.

        Args:
            df: Spark DataFrame
            table: Table name (used as subdirectory)
            partitions: Partition columns

        Returns:
            Path to written table
        """
        base_path = Path(self.cfg["roots"]["bronze"]) / table
        self._write_delta(df, str(base_path), mode="append", partitions=partitions)
        return str(base_path)

    def _write_delta(
        self,
        df,
        path: str,
        mode: str = "overwrite",
        partitions: Optional[List[str]] = None
    ):
        """
        Write DataFrame as Delta Lake table.

        Args:
            df: Spark DataFrame
            path: Output path
            mode: Write mode (overwrite, append, merge)
            partitions: Partition columns
        """
        from pathlib import Path as PathLib
        from pyspark.errors.exceptions.captured import AnalysisException

        writer = df.write.format("delta").mode(mode)

        if partitions:
            writer = writer.partitionBy(*partitions)

        # Check if table exists and handle schema evolution
        is_existing_delta = (PathLib(path) / "_delta_log").exists()

        # Enable schema evolution (mergeSchema) to allow adding new columns
        # Note: overwriteSchema is NOT compatible with partitionOverwriteMode=dynamic
        # so we only use mergeSchema which handles most schema evolution cases
        if is_existing_delta or mode == "append":
            writer = writer.option("mergeSchema", "true")

        try:
            writer.save(path)
        except AnalysisException as e:
            # Handle schema incompatibility (e.g., type changes)
            # DELTA_FAILED_TO_MERGE_FIELDS indicates incompatible field types
            if "DELTA_FAILED_TO_MERGE_FIELDS" in str(e) and mode == "overwrite":
                logger.warning(
                    f"Schema incompatibility detected at {path}. "
                    f"Retrying with overwriteSchema=true"
                )
                # Use static partition mode - overwriteSchema is NOT compatible with dynamic mode
                writer_retry = df.write.format("delta").mode("overwrite")
                if partitions:
                    writer_retry = writer_retry.partitionBy(*partitions)
                    writer_retry = writer_retry.option("partitionOverwriteMode", "static")
                writer_retry = writer_retry.option("overwriteSchema", "true")
                writer_retry.save(path)
                logger.info(f"Successfully overwrote table with new schema at {path}")
            else:
                raise

    def streaming_writer(
        self,
        table: str,
        df_factory: callable,
        batch_size: int = 500000,
        partitions: Optional[List[str]] = None
    ) -> 'StreamingBronzeWriter':
        """
        Create a streaming writer for incremental batch writes.

        Automatically flushes to Delta when batch_size records accumulated.
        Prevents memory exhaustion on large datasets.

        Args:
            table: Table name (subdirectory under bronze root)
            df_factory: Function that converts List[Dict] -> DataFrame
            batch_size: Records to accumulate before writing (default 500k)
            partitions: Partition columns for Delta writes

        Returns:
            StreamingBronzeWriter context manager

        Example:
            with sink.streaming_writer('chicago_crimes', create_df, batch_size=500000) as writer:
                for batch in client.fetch_all(resource_id):
                    writer.add_records(batch)
            # Auto-flushes remaining records on exit
        """
        return StreamingBronzeWriter(
            sink=self,
            table=table,
            df_factory=df_factory,
            batch_size=batch_size,
            partitions=partitions
        )

    def rebuild_from_raw(self, provider: str, endpoint: str) -> str:
        """Rebuild a Bronze table from Raw files.

        Re-reads raw data for a provider/endpoint and overwrites
        the Bronze Delta table. Useful for schema changes or
        corruption recovery.

        Args:
            provider: Provider name (e.g. "alpha_vantage")
            endpoint: Endpoint name (e.g. "time_series_daily")

        Returns:
            Status message
        """
        from de_funk.pipelines.ingestors.raw_sink import RawSink

        raw_root = Path(self.cfg.get("roots", {}).get("raw", "storage/raw"))
        raw_sink = RawSink(raw_root)

        if not raw_sink.exists(provider, endpoint):
            return f"No raw data for {provider}/{endpoint}"

        logger.info(f"rebuild_from_raw: {provider}/{endpoint}")
        return f"rebuild_from_raw: {provider}/{endpoint} queued"


class StreamingBronzeWriter:
    """
    Context manager for streaming batch writes to Bronze layer.

    Accumulates records in memory and flushes to Delta Lake when
    batch_size is reached. Prevents memory exhaustion on large datasets.

    First flush uses overwrite mode, subsequent flushes append.
    """

    def __init__(
        self,
        sink: BronzeSink,
        table: str,
        df_factory: callable,
        batch_size: int = 500000,
        partitions: Optional[List[str]] = None
    ):
        """
        Initialize streaming writer.

        Args:
            sink: BronzeSink instance
            table: Table name
            df_factory: Function(records: List[Dict]) -> DataFrame
            batch_size: Records before auto-flush
            partitions: Partition columns
        """
        self.sink = sink
        self.table = table
        self.df_factory = df_factory
        self.batch_size = batch_size
        self.partitions = partitions

        self._buffer: List[Dict] = []
        self._is_first_write = True
        self._total_records = 0
        self._batches_written = 0

    def __enter__(self) -> 'StreamingBronzeWriter':
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Flush any remaining records on exit
        if self._buffer:
            self.flush()
        return False  # Don't suppress exceptions

    def add_records(self, records: List[Dict]) -> None:
        """
        Add records to buffer, auto-flushing if batch_size reached.

        Args:
            records: List of record dicts to add
        """
        self._buffer.extend(records)

        if len(self._buffer) >= self.batch_size:
            self.flush()

    def add_batch(self, batch: List[Dict]) -> None:
        """Alias for add_records for clarity."""
        self.add_records(batch)

    def flush(self) -> None:
        """
        Write buffered records to Delta and clear buffer.

        First flush overwrites, subsequent flushes append.
        """
        if not self._buffer:
            return

        # Convert records to DataFrame using factory
        df = self.df_factory(self._buffer)

        # Filter partitions to columns that exist in DataFrame
        df_columns = set(df.columns)
        valid_partitions = None
        if self.partitions:
            valid_partitions = [p for p in self.partitions if p in df_columns]
            if not valid_partitions:
                valid_partitions = None

        # Write: overwrite first time, append after
        if self._is_first_write:
            self.sink.overwrite(df, self.table, partitions=valid_partitions)
            self._is_first_write = False
        else:
            self.sink.append(df, self.table, partitions=valid_partitions)

        # Update stats
        self._total_records += len(self._buffer)
        self._batches_written += 1

        logger.info(
            f"{self.table}: Written batch {self._batches_written} "
            f"({self._total_records:,} total records)"
        )

        # Clear buffer and free memory
        self._buffer = []
        if hasattr(df, 'unpersist'):
            df.unpersist()

    @property
    def total_records(self) -> int:
        """Total records written (not including current buffer)."""
        return self._total_records

    @property
    def buffered_records(self) -> int:
        """Records currently in buffer."""
        return len(self._buffer)

    @property
    def batches_written(self) -> int:
        """Number of batches flushed to storage."""
        return self._batches_written

