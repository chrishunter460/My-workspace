"""
Unified Ingestor Engine with Async Writes.

Provider-agnostic ingestion engine that decouples fetching from writing
using a ThreadPoolExecutor for parallel I/O. This improves throughput
by overlapping API fetches with Delta Lake writes.

Architecture:
    ┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
    │   Fetch Thread  │───▶│  In-Memory Queue │───▶│  Writer Thread  │
    │   (API calls)   │    │  (bounded, ~3)   │    │  (Delta writes) │
    └─────────────────┘    └──────────────────┘    └─────────────────┘

Benefits:
    - ~2-3x throughput improvement (fetch + write overlap)
    - Backpressure prevents OOM (bounded pending writes)
    - Reusable pattern for Airflow migration
    - Same interface as synchronous version

Usage:
    from de_funk.pipelines.base.ingestor_engine import IngestorEngine
    from de_funk.pipelines.providers.alpha_vantage import create_alpha_vantage_provider

    provider = create_alpha_vantage_provider(spark, docs_path)
    engine = IngestorEngine(provider, storage_cfg)

    # Ingest all work items (data types or endpoints)
    results = engine.run()

    # Or specific work items
    results = engine.run(work_items=["prices", "reference"])

Author: de_Funk Team
"""

from __future__ import annotations

import gc
import time
import threading
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
from queue import Queue, Empty

from de_funk.pipelines.base.provider import BaseProvider, WorkItemResult
from de_funk.pipelines.ingestors.bronze_sink import BronzeSink
from de_funk.config.logging import get_logger

logger = get_logger(__name__)


@dataclass
class IngestionResults:
    """Results from an ingestion run."""
    work_items: List[str] = field(default_factory=list)
    total_work_items: int = 0
    completed_work_items: int = 0
    total_records: int = 0
    total_errors: int = 0
    results: Dict[str, WorkItemResult] = field(default_factory=dict)
    elapsed_seconds: float = 0.0

    def add_result(self, result: WorkItemResult) -> None:
        """Add a work item result."""
        if result is None:
            logger.warning("add_result called with None - this is a bug in the caller")
            return

        self.results[result.work_item] = result
        self.work_items.append(result.work_item)

        if result.success:
            self.completed_work_items += 1
            self.total_records += result.record_count
        else:
            self.total_errors += 1

    def summary(self) -> Dict[str, Any]:
        """Get summary statistics."""
        return {
            "total_work_items": self.total_work_items,
            "completed": self.completed_work_items,
            "failed": self.total_errors,
            "total_records": self.total_records,
            "elapsed_seconds": self.elapsed_seconds,
            "records_per_second": (
                self.total_records / self.elapsed_seconds
                if self.elapsed_seconds > 0 else 0
            ),
        }

    def print_summary(self) -> None:
        """Print human-readable summary."""
        print(f"\n{'=' * 60}")
        print("INGESTION SUMMARY")
        print(f"{'=' * 60}")
        print(f"  Work items: {self.completed_work_items}/{self.total_work_items} completed")
        print(f"  Records: {self.total_records:,}")
        print(f"  Errors: {self.total_errors}")
        print(f"  Time: {self.elapsed_seconds:.1f}s")
        if self.elapsed_seconds > 0:
            print(f"  Throughput: {self.total_records / self.elapsed_seconds:,.0f} records/sec")
        print(f"{'=' * 60}\n")


@dataclass
class WriteTask:
    """A queued write task."""
    df: Any  # Spark DataFrame
    table_name: str
    partitions: Optional[List[str]]
    record_count: int
    work_item: str


class IngestorEngine:
    """
    Unified ingestion engine with async writes.

    Decouples data fetching from Delta Lake writes using a ThreadPoolExecutor.
    This allows fetching the next batch while the previous batch is being written,
    improving throughput by 2-3x for I/O bound workloads.

    Features:
        - Async writes via ThreadPoolExecutor
        - Bounded queue with backpressure (prevents OOM)
        - Same interface as synchronous version
        - Reusable pattern for Airflow migration

    Example:
        provider = create_socrata_provider("chicago", spark=spark, docs_path=docs_path)
        engine = IngestorEngine(provider, storage_cfg)

        # Ingest all endpoints with async writes
        results = engine.run(write_batch_size=500000)
    """

    # Class-level executor shared across instances (reusable for Airflow)
    _executor: Optional[ThreadPoolExecutor] = None
    _executor_lock = threading.Lock()

    def __init__(
        self,
        provider: BaseProvider = None,
        storage_cfg: Dict = None,
        max_pending_writes: int = 2,
        writer_threads: int = 2,
        session=None,
    ):
        """
        Initialize the ingestion engine.

        Preferred: pass session (IngestSession) which provides storage_router,
        engine, and provider/endpoint config lookup.

        Legacy: pass provider + storage_cfg directly.

        Args:
            provider: Provider instance (legacy) or None if using session
            storage_cfg: Storage configuration dict (legacy) or None if using session
            max_pending_writes: Max writes to queue before blocking (backpressure)
            writer_threads: Number of writer threads in pool
            session: IngestSession from DeFunk.ingest_session()
        """
        self.session = session
        self.provider = provider
        self.max_pending_writes = max_pending_writes
        self.writer_threads = writer_threads

        # Resolve storage config from session or direct param
        if session is not None:
            self.storage_cfg = session._storage_config
            self.storage_router = session.storage_router
        else:
            self.storage_cfg = storage_cfg or {}
            from de_funk.core.storage import StorageRouter
            self.storage_router = StorageRouter(self.storage_cfg)

        # Create sinks using storage_router paths
        self.sink = BronzeSink(self.storage_cfg, session=session)

        from de_funk.pipelines.ingestors.raw_sink import RawSink
        self.raw_sink = RawSink(raw_root=self.storage_router.raw_root)

        # Track pending writes per work item
        self._pending_futures: List[Future] = []
        self._write_errors: List[str] = []

    @classmethod
    def from_session(cls, session, provider: BaseProvider,
                     max_pending_writes: int = 2, writer_threads: int = 2):
        """Create IngestorEngine from an IngestSession.

        Usage:
            app = DeFunk.from_config()
            session = app.ingest_session()
            provider = create_socrata_provider("chicago", spark=spark, docs_path=docs_path)
            engine = IngestorEngine.from_session(session, provider)
            engine.run(work_items=["crimes"])
        """
        return cls(
            provider=provider,
            session=session,
            max_pending_writes=max_pending_writes,
            writer_threads=writer_threads,
        )

    @classmethod
    def get_executor(cls, max_workers: int = 2) -> ThreadPoolExecutor:
        """
        Get or create shared ThreadPoolExecutor.

        Shared across all IngestorEngine instances for efficiency.
        Can be reused when migrating to Airflow workers.

        Args:
            max_workers: Number of writer threads

        Returns:
            ThreadPoolExecutor instance
        """
        with cls._executor_lock:
            if cls._executor is None or cls._executor._shutdown:
                cls._executor = ThreadPoolExecutor(
                    max_workers=max_workers,
                    thread_name_prefix="delta_writer"
                )
                logger.info(f"Created shared ThreadPoolExecutor with {max_workers} workers")
            return cls._executor

    @classmethod
    def shutdown_executor(cls, wait: bool = True) -> None:
        """Shutdown the shared executor."""
        with cls._executor_lock:
            if cls._executor is not None:
                cls._executor.shutdown(wait=wait)
                cls._executor = None
                logger.info("Shutdown shared ThreadPoolExecutor")

    def run(
        self,
        work_items: List[str] = None,
        write_batch_size: int = 500000,
        max_records: Optional[int] = None,
        silent: bool = False,
        async_writes: bool = True,
        **kwargs
    ) -> IngestionResults:
        """
        Run ingestion for work items.

        Args:
            work_items: List of work items to ingest (None = all from provider)
            write_batch_size: Records to buffer before each Delta write (default 500k).
                Used in both sync and async modes to keep memory bounded.
            max_records: Max records per work item (None = no limit)
            silent: Suppress progress output
            async_writes: Enable async writes (default True for ~2-3x throughput).
                Async mode overlaps fetch with write operations using chunked writes.
            **kwargs: Provider-specific options passed to fetch()

        Returns:
            IngestionResults with summary and per-item results
        """
        start_time = time.time()

        # Get work items from provider if not specified
        if work_items is None:
            work_items = self.provider.list_work_items(**kwargs)

        results = IngestionResults(total_work_items=len(work_items))

        if not silent:
            print(f"\n{'=' * 60}")
            print(f"INGESTOR ENGINE: {self.provider.provider_id.upper()}")
            print(f"{'=' * 60}")
            print(f"  Work items: {len(work_items)}")
            print(f"  Mode: {'async (chunked)' if async_writes else 'sync'}")
            print(f"  Batch size: {write_batch_size:,} records")
            if max_records:
                print(f"  Max records per item: {max_records:,}")
            print()

        # Process each work item
        for i, work_item in enumerate(work_items):
            if not silent:
                print(f"[{i+1}/{len(work_items)}] {work_item}...", end=" ", flush=True)

            if async_writes:
                result = self._ingest_work_item_async(
                    work_item=work_item,
                    write_batch_size=write_batch_size,
                    max_records=max_records,
                    **kwargs
                )
            else:
                result = self._ingest_work_item_sync(
                    work_item=work_item,
                    write_batch_size=write_batch_size,
                    max_records=max_records,
                    **kwargs
                )

            results.add_result(result)

            if not silent:
                if result.success:
                    print(f"✓ {result.record_count:,} records")
                else:
                    print(f"✗ {result.error}")

        # Wait for all pending async writes to complete
        if async_writes and self._pending_futures:
            if not silent:
                print("Waiting for async writes to complete...", end=" ", flush=True)
            write_errors = []
            for future in self._pending_futures:
                try:
                    future.result()
                except Exception as e:
                    write_errors.append(str(e)[:100])
                    logger.error(f"Async write failed: {e}")
            self._pending_futures = []

            if write_errors:
                if not silent:
                    print(f"✗ {len(write_errors)} write errors")
                results.total_errors += len(write_errors)
            else:
                if not silent:
                    print("✓")

        results.elapsed_seconds = time.time() - start_time

        # Final cleanup after all work items complete
        # Critical when multiple providers share same Spark session
        self._cleanup_spark_memory()
        logger.info(f"Final cleanup complete for {self.provider.provider_id}")

        if not silent:
            results.print_summary()

        return results

    def _wait_for_pending_writes(self, max_pending: int = None) -> None:
        """
        Wait until pending writes are below threshold (backpressure).

        Args:
            max_pending: Max pending writes to allow (None = wait for all)
        """
        if max_pending is None:
            max_pending = 0

        # Clean up completed futures
        self._pending_futures = [f for f in self._pending_futures if not f.done()]

        # Wait if too many pending
        while len(self._pending_futures) > max_pending:
            # Check for any errors in completed futures
            completed = [f for f in self._pending_futures if f.done()]
            for f in completed:
                try:
                    f.result()  # Raises if write failed
                except Exception as e:
                    self._write_errors.append(str(e))
                    logger.error(f"Async write failed: {e}")

            self._pending_futures = [f for f in self._pending_futures if not f.done()]

            if len(self._pending_futures) > max_pending:
                time.sleep(0.1)

    def _cleanup_spark_memory(self) -> None:
        """
        Force cleanup of Spark memory after a work item completes.

        Clears Spark's in-memory cache, Delta Lake cache, and triggers GC.
        Critical for large endpoints like crimes (8M+ records).
        """
        try:
            # Get Spark session and clear cache
            from pyspark.sql import SparkSession
            spark = SparkSession.getActiveSession()
            if spark:
                # Clear user-facing cache
                spark.catalog.clearCache()

                # Clear Delta Lake's internal cache
                try:
                    spark.sql("CLEAR CACHE")
                except Exception:
                    pass  # May fail if no cached tables

                # Clear Spark SQL's internal state
                try:
                    spark._jsparkSession.sharedState().cacheManager().clearCache()
                except Exception:
                    pass  # May not be available in all Spark versions

                # Force JVM garbage collection (call twice for thorough cleanup)
                spark._jvm.System.gc()
                spark._jvm.System.gc()
                logger.debug("Cleared Spark/Delta cache and triggered JVM GC")
        except Exception as e:
            logger.debug(f"Spark cleanup (non-critical): {e}")

        # Python garbage collection (full collection across all generations)
        gc.collect(0)
        gc.collect(1)
        gc.collect(2)

    def _save_raw(self, records: list, provider_id: str, work_item: str,
                  partition: str = "") -> None:
        """Save raw API records to the Raw tier before Bronze transformation."""
        try:
            self.raw_sink.write(records, provider_id, work_item, partition)
            logger.debug(f"Raw saved: {provider_id}/{work_item} ({len(records)} records)")
        except Exception as e:
            logger.warning(f"Raw save failed for {provider_id}/{work_item}: {e}")

    def _archive_raw(self, table_name: str) -> None:
        """Archive raw data to compressed tar.gz after Bronze write.

        Archives per-provider: raw/{provider}/{endpoint}/ → raw_archive/{provider}_{endpoint}_{date}.tar.gz
        """
        import tarfile
        from datetime import datetime

        # Parse provider/endpoint from table_name (e.g. "chicago/community_areas")
        parts = table_name.split("/")
        if len(parts) < 2:
            return

        provider = parts[0]
        endpoint = parts[1]
        raw_path = Path(self.raw_sink.raw_root) / provider / endpoint

        if not raw_path.exists() or not any(raw_path.iterdir()):
            return

        archive_dir = Path(self.raw_sink.raw_root).parent / "raw_archive"
        archive_dir.mkdir(parents=True, exist_ok=True)

        archive_name = f"{provider}_{endpoint}_{datetime.now().strftime('%Y%m%d')}.tar.gz"
        archive_path = archive_dir / archive_name

        try:
            with tarfile.open(archive_path, "w:gz") as tar:
                tar.add(str(raw_path), arcname=f"{provider}/{endpoint}")
            logger.info(f"Archived raw: {archive_path} ({archive_path.stat().st_size / 1024:.0f} KB)")
        except Exception as e:
            logger.warning(f"Raw archive failed for {table_name}: {e}")

    def _async_write(
        self,
        df,
        table_name: str,
        partitions: Optional[List[str]],
        mode: str = "overwrite",
        write_strategy: str = "append",
        key_columns: Optional[List[str]] = None,
        date_column: Optional[str] = None
    ) -> int:
        """
        Write DataFrame to Delta Lake (runs in background thread).

        Args:
            df: Spark DataFrame to write
            table_name: Target table name
            partitions: Partition columns
            mode: Write mode - "overwrite" or "append" (for upsert strategy)
            write_strategy: "append" (preserves existing) or "upsert" (overwrites first chunk)
            key_columns: Columns for deduplication (required for append strategy)
            date_column: Date column for append_immutable (optional)

        Returns:
            Number of records written
        """
        try:
            count = df.count()

            if write_strategy == "append" and key_columns:
                # Use append_immutable for time series data - preserves existing records
                self.sink.append_immutable(
                    df, table_name,
                    key_columns=key_columns,
                    partitions=partitions,
                    date_column=date_column or "trade_date"
                )
                logger.info(f"Wrote {table_name}: {count:,} records (append_immutable)")
            elif mode == "append":
                self.sink.append(df, table_name, partitions=partitions)
                logger.info(f"Wrote {table_name}: {count:,} records (mode=append)")
            else:
                self.sink.overwrite(df, table_name, partitions=partitions)
                logger.info(f"Wrote {table_name}: {count:,} records (mode=overwrite)")

            # Archive raw data after successful Bronze write
            self._archive_raw(table_name)

            return count
        finally:
            # CRITICAL: Release Spark memory after write completes
            try:
                df.unpersist()
            except Exception:
                pass  # DataFrame may not be cached
            # Force Python GC to release any remaining references
            gc.collect()

    def _ingest_bulk_from_raw(
        self,
        work_item: str,
        raw_path: str,
        table_name: str,
        partitions: Optional[List[str]],
        write_strategy: str = "append",
        key_columns: Optional[List[str]] = None,
        date_column: Optional[str] = None
    ) -> WorkItemResult:
        """
        PATH 1: Bulk insert from raw staging files.

        Reads all raw files at once with Spark, bulk writes to Bronze.
        Provider handles format-specific reading (CSV vs JSON, nested structures).

        Args:
            work_item: Work item identifier
            raw_path: Path or glob pattern to raw files
            table_name: Target Bronze table
            partitions: Partition columns
            write_strategy: "append" or "overwrite"
            key_columns: Columns for deduplication
            date_column: Date column for append_immutable

        Returns:
            WorkItemResult with status and record count
        """
        try:
            # Provider reads raw files and returns DataFrame
            # (handles format-specific details: CSV/JSON, nested maps, etc.)
            df = self.provider.read_raw_as_df(work_item, raw_path)

            if df is None:
                logger.warning(f"{work_item}: read_raw_as_df returned None")
                return None

            # Validate partitions
            validated_partitions = self._validate_partitions(
                partitions, df.columns, work_item
            )

            # Repartition large DataFrames for write parallelism
            # CSV reads often result in a single partition - spread work across executors
            current_partitions = df.rdd.getNumPartitions()
            if current_partitions <= 2:
                # Estimate row count from first partition to avoid full count()
                # Target ~1M rows per partition for efficient Delta writes
                target_partitions = max(
                    int(self.provider.spark.conf.get("spark.sql.shuffle.partitions", "200")),
                    16  # Minimum parallelism
                )
                if validated_partitions:
                    # Use partition columns for hash-based repartition (more efficient for writes)
                    logger.info(f"{work_item}: Repartitioning to {target_partitions} partitions by {validated_partitions}")
                    df = df.repartition(target_partitions, *validated_partitions)
                else:
                    # Round-robin repartition
                    logger.info(f"{work_item}: Repartitioning to {target_partitions} partitions (round-robin)")
                    df = df.repartition(target_partitions)

            # Write to Bronze
            logger.info(f"{work_item}: Writing {table_name} (strategy={write_strategy})")
            if write_strategy == "append" and key_columns:
                self.sink.append_immutable(
                    df, table_name,
                    key_columns=key_columns,
                    partitions=validated_partitions,
                    date_column=date_column or "trade_date"
                )
            else:
                self.sink.overwrite(df, table_name, partitions=validated_partitions)

            total_records = df.count()
            logger.info(f"{work_item}: BULK complete - {total_records:,} records")

            # Cleanup
            try:
                df.unpersist()
            except Exception:
                pass
            self._cleanup_spark_memory()

            return WorkItemResult(
                work_item=work_item,
                success=True,
                record_count=total_records,
                table_path=str(self.sink.cfg["roots"]["bronze"]) + "/" + table_name
            )

        except Exception as e:
            logger.error(f"BULK failed for {work_item}: {e}", exc_info=True)
            return WorkItemResult(
                work_item=work_item,
                success=False,
                error=str(e)[:200]
            )

    def _ingest_work_item_async(
        self,
        work_item: str,
        write_batch_size: int,
        max_records: Optional[int] = None,
        **kwargs
    ) -> WorkItemResult:
        """
        Ingest a single work item using the best available method.

        Method selection (in order of preference):
        1. SPARK-NATIVE PATH (if provider has fetch_as_dataframe):
           - Optionally calls populate_raw_cache() first (Alpha Vantage: API → raw JSON)
           - Spark reads all files at once (CSV or JSON)
           - Single DataFrame write to Delta
           - 10-50x faster for large datasets

        2. PYTHON BATCHING (fallback for providers without fetch_as_dataframe):
           - Fetches records in batches via provider.fetch()
           - Normalizes with provider.normalize()
           - Async writes to Delta

        Args:
            work_item: Work item identifier
            write_batch_size: Records to buffer before each write (Python path only)
            max_records: Max records to fetch (disables Spark-native path if set)
            **kwargs: Provider-specific options

        Returns:
            WorkItemResult with status and record count
        """
        try:
            # Get table configuration from provider
            table_name = self.provider.get_table_name(work_item)
            partitions = self.provider.get_partitions(work_item)
            write_strategy = self.provider.get_write_strategy(work_item)
            key_columns = self.provider.get_key_columns(work_item)
            date_column = self.provider.get_date_column(work_item)

            logger.info(f"{work_item}: write_strategy={write_strategy}, table={table_name}")

            # =========================================================================
            # PATH 1: BULK INSERT (raw staging)
            # =========================================================================
            # Use when: Raw files as staging ground, Spark reads all at once
            # Provider implements:
            #   - populate_raw_cache(work_item) -> downloads raw files (optional)
            #   - get_raw_path(work_item) -> path/glob pattern
            #   - read_raw_as_df(work_item, raw_path) -> DataFrame
            #
            if max_records is None and hasattr(self.provider, 'get_raw_path'):

                # Step 1: Populate raw cache if provider supports it
                # (Alpha Vantage: API → JSON files, Socrata: API → CSV file)
                if hasattr(self.provider, 'populate_raw_cache'):
                    logger.info(f"{work_item}: Populating raw cache")
                    stats = self.provider.populate_raw_cache(work_item, **kwargs)
                    if stats:
                        logger.info(
                            f"{work_item}: Cache - "
                            f"cached: {stats.get('cached', 0)}, "
                            f"fetched: {stats.get('fetched', 0)}, "
                            f"failed: {stats.get('failed', 0)}"
                        )

                # Step 2: Check if raw files exist
                raw_path = self.provider.get_raw_path(work_item)

                if raw_path:
                    logger.info(f"{work_item}: BULK path - {raw_path}")
                    result = self._ingest_bulk_from_raw(
                        work_item, raw_path, table_name, partitions,
                        write_strategy, key_columns, date_column
                    )
                    if result is None:
                        return WorkItemResult(
                            work_item=work_item,
                            success=False,
                            error="BULK read_raw_as_df returned None"
                        )
                    return result

            # =========================================================================
            # PATH 2: INCREMENTAL (fetch and stream)
            # =========================================================================
            # Use when: Fetching new/changed records, insert as batches arrive
            # Provider implements: fetch(work_item) -> yields batches
            #
            logger.info(f"{work_item}: INCREMENTAL path - fetching and streaming")

            executor = self.get_executor(self.writer_threads)

            # Reset write errors for this work item
            self._write_errors = []

            # Track state for chunked writes
            buffer = []
            total_records = 0
            chunk_count = 0
            validated_partitions = None  # Cache validated partitions after first chunk

            for batch in self.provider.fetch(
                work_item,
                max_records=max_records,
                **kwargs
            ):
                # Save raw before any transformation
                self._save_raw(batch, self.provider.provider_id, work_item)
                buffer.extend(batch)

                # When buffer reaches batch size, write it
                if len(buffer) >= write_batch_size:
                    # Wait for backpressure before queueing more writes
                    self._wait_for_pending_writes(self.max_pending_writes)

                    # Normalize buffer to DataFrame
                    df = self.provider.normalize(buffer, work_item)

                    # Validate partitions on first chunk only
                    if validated_partitions is None:
                        validated_partitions = self._validate_partitions(
                            partitions, df.columns, work_item
                        )

                    # Determine write mode based on strategy
                    # append strategy: always append (append_immutable handles dedup)
                    # upsert strategy: overwrite first chunk, then append
                    if write_strategy == "append":
                        mode = "append"  # append_immutable will handle dedup
                    else:
                        mode = "overwrite" if chunk_count == 0 else "append"

                    # Queue async write
                    future = executor.submit(
                        self._async_write,
                        df,
                        table_name,
                        validated_partitions,
                        mode,
                        write_strategy,
                        key_columns,
                        date_column
                    )
                    self._pending_futures.append(future)

                    # Wait for first write to complete before appends
                    # This prevents Delta protocol conflicts on table creation
                    if chunk_count == 0:
                        self._wait_for_pending_writes(0)

                    total_records += len(buffer)
                    chunk_count += 1
                    logger.info(
                        f"{work_item}: queued chunk {chunk_count} "
                        f"({len(buffer):,} records, strategy={write_strategy})"
                    )

                    # Clear buffer and free memory
                    buffer.clear()
                    gc.collect()

            # Write any remaining records in buffer
            if buffer:
                self._wait_for_pending_writes(self.max_pending_writes)

                df = self.provider.normalize(buffer, work_item)

                if validated_partitions is None:
                    validated_partitions = self._validate_partitions(
                        partitions, df.columns, work_item
                    )

                # Determine write mode based on strategy
                if write_strategy == "append":
                    mode = "append"  # append_immutable will handle dedup
                else:
                    mode = "overwrite" if chunk_count == 0 else "append"

                future = executor.submit(
                    self._async_write,
                    df,
                    table_name,
                    validated_partitions,
                    mode,
                    write_strategy,
                    key_columns,
                    date_column
                )
                self._pending_futures.append(future)

                total_records += len(buffer)
                chunk_count += 1
                logger.info(
                    f"{work_item}: queued final chunk {chunk_count} "
                    f"({len(buffer):,} records, strategy={write_strategy})"
                )

            # Wait for all pending writes for this work item to complete
            # This ensures memory is released before starting next work item
            self._wait_for_pending_writes(0)  # Wait for all

            # Force cleanup of any remaining Spark memory
            self._cleanup_spark_memory()

            if total_records == 0:
                return WorkItemResult(
                    work_item=work_item,
                    success=True,
                    record_count=0,
                    table_path=str(self.sink.cfg["roots"]["bronze"]) + "/" + table_name
                )

            return WorkItemResult(
                work_item=work_item,
                success=True,
                record_count=total_records,
                table_path=str(self.sink.cfg["roots"]["bronze"]) + "/" + table_name
            )

        except Exception as e:
            logger.error(f"Failed to ingest {work_item}: {e}", exc_info=True)
            return WorkItemResult(
                work_item=work_item,
                success=False,
                error=str(e)[:200]
            )

    def _validate_partitions(
        self,
        partitions: Optional[List[str]],
        df_columns: List[str],
        work_item: str
    ) -> Optional[List[str]]:
        """Validate partition columns exist in DataFrame schema."""
        if not partitions:
            return None

        df_columns_set = set(df_columns)
        valid_partitions = [p for p in partitions if p in df_columns_set]

        if valid_partitions != partitions:
            missing = set(partitions) - set(valid_partitions)
            logger.warning(
                f"Partition columns {missing} not found in {work_item} schema, "
                f"using {valid_partitions or 'no partitions'}"
            )

        return valid_partitions if valid_partitions else None

    def _ingest_work_item_sync(
        self,
        work_item: str,
        write_batch_size: int,
        max_records: Optional[int] = None,
        **kwargs
    ) -> WorkItemResult:
        """
        Ingest a single work item synchronously (original behavior).

        Uses StreamingBronzeWriter for memory-safe writes.
        Kept for compatibility and debugging.

        Args:
            work_item: Work item identifier
            write_batch_size: Records to buffer before write
            max_records: Max records to fetch
            **kwargs: Provider-specific options

        Returns:
            WorkItemResult with status and record count
        """
        try:
            # Get table configuration from provider
            table_name = self.provider.get_table_name(work_item)
            partitions = self.provider.get_partitions(work_item)

            # Create DataFrame factory using provider's normalize method
            def df_factory(records):
                return self.provider.normalize(records, work_item)

            # Use StreamingBronzeWriter for memory-safe writes
            with self.sink.streaming_writer(
                table=table_name,
                df_factory=df_factory,
                batch_size=write_batch_size,
                partitions=partitions
            ) as writer:
                # Fetch data and stream to writer
                for batch in self.provider.fetch(
                    work_item,
                    max_records=max_records,
                    **kwargs
                ):
                    writer.add_batch(batch)

                total_records = writer.total_records + writer.buffered_records

            return WorkItemResult(
                work_item=work_item,
                success=True,
                record_count=total_records,
                table_path=str(self.sink.cfg["roots"]["bronze"]) + "/" + table_name
            )

        except Exception as e:
            logger.error(f"Failed to ingest {work_item}: {e}", exc_info=True)
            return WorkItemResult(
                work_item=work_item,
                success=False,
                error=str(e)[:200]
            )

    def run_with_discovery(
        self,
        write_batch_size: int = 500000,
        max_records: Optional[int] = None,
        silent: bool = False,
        **kwargs
    ) -> IngestionResults:
        """
        Run ingestion with automatic work item discovery.

        Convenience method that calls list_work_items() and then run().

        Args:
            write_batch_size: Records to buffer before write
            max_records: Max records per work item
            silent: Suppress output
            **kwargs: Provider-specific options

        Returns:
            IngestionResults
        """
        return self.run(
            work_items=None,  # Will be discovered
            write_batch_size=write_batch_size,
            max_records=max_records,
            silent=silent,
            **kwargs
        )


def create_engine(
    provider_name: str,
    storage_cfg: Dict,
    spark=None,
    docs_path: Optional[Path] = None,
    max_pending_writes: int = 2,
    writer_threads: int = 2,
) -> IngestorEngine:
    """
    Factory function to create an IngestorEngine for any provider.

    Configuration is loaded from markdown documentation (single source of truth).

    Args:
        provider_name: Provider name (e.g., "alpha_vantage", "chicago", "cook_county")
        storage_cfg: Storage configuration dict
        spark: SparkSession
        docs_path: Path to repo root
        max_pending_writes: Max writes to queue before blocking
        writer_threads: Number of writer threads

    Returns:
        IngestorEngine wrapping the appropriate provider
    """
    if provider_name == "alpha_vantage":
        from de_funk.pipelines.providers.alpha_vantage.alpha_vantage_provider import (
            create_alpha_vantage_provider
        )
        provider = create_alpha_vantage_provider(spark, docs_path)
        return IngestorEngine(
            provider, storage_cfg,
            max_pending_writes=max_pending_writes,
            writer_threads=writer_threads
        )

    elif provider_name in ("chicago", "chicago_data_portal"):
        from de_funk.pipelines.base.socrata_provider import create_socrata_provider
        storage_path = Path(storage_cfg.get("roots", {}).get("bronze", "storage/bronze")).parent
        provider = create_socrata_provider("chicago", spark=spark, docs_path=docs_path, storage_path=storage_path)
        return IngestorEngine(
            provider, storage_cfg,
            max_pending_writes=max_pending_writes,
            writer_threads=writer_threads
        )

    elif provider_name in ("cook_county", "cook_county_data_portal"):
        from de_funk.pipelines.base.socrata_provider import create_socrata_provider
        storage_path = Path(storage_cfg.get("roots", {}).get("bronze", "storage/bronze")).parent
        provider = create_socrata_provider("cook_county", spark=spark, docs_path=docs_path, storage_path=storage_path)
        return IngestorEngine(
            provider, storage_cfg,
            max_pending_writes=max_pending_writes,
            writer_threads=writer_threads
        )

    else:
        raise ValueError(f"Unknown provider: {provider_name}")
