"""
DuckDB connection implementation with Delta Lake support.

DuckDB is excellent for analytics workloads and can read Parquet and Delta Lake files directly.
Much faster startup than Spark for single-node operations.

Delta Lake Support:
- ACID transactions
- Time travel queries
- Schema evolution
- Merge/upsert operations
"""

from typing import Dict, Any, Optional, List
import pandas as pd
from pathlib import Path

from de_funk.config.logging import get_logger

try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False

try:
    from deltalake import DeltaTable, write_deltalake
    DELTA_AVAILABLE = True
except ImportError:
    DELTA_AVAILABLE = False

from .connection import DataConnection

logger = get_logger(__name__)


class DuckDBConnection(DataConnection):
    """
    DuckDB connection for analytics queries with Delta Lake support.

    Benefits:
    - Fast startup (no Spark overhead)
    - Native Parquet and Delta Lake support
    - Great for interactive/notebook workloads
    - SQL-based queries
    - ACID transactions with Delta
    - Time travel queries
    - Can still use Spark for heavy ETL
    """

    def __init__(self, db_path: str = ":memory:", read_only: bool = False, enable_delta: bool = True, auto_init_views: bool = True):
        """
        Initialize DuckDB connection with optional Delta Lake support.

        Args:
            db_path: Path to DuckDB database file (":memory:" for in-memory)
            read_only: Whether to open in read-only mode
            enable_delta: Whether to enable Delta Lake extension (default: True)
            auto_init_views: Whether to automatically create v2.0 model views (default: True)
        """
        if not DUCKDB_AVAILABLE:
            raise ImportError(
                "DuckDB is not installed. Install it with: pip install duckdb"
            )

        self.db_path = db_path
        self.conn = duckdb.connect(db_path, read_only=read_only)
        self._cached_tables = {}
        self.delta_enabled = False

        # Enable Delta Lake extension if requested
        if enable_delta:
            self._enable_delta_extension()

        # Auto-initialize views for v2.0 models (if persistent database and not read-only)
        if auto_init_views and db_path != ":memory:" and not read_only:
            self._init_model_views()

    def _enable_delta_extension(self):
        """
        Enable DuckDB Delta extension.

        Installs and loads the Delta extension for reading/writing Delta Lake tables.
        """
        try:
            # Install delta extension (only needed once per database)
            self.conn.execute("INSTALL delta")
            # Load delta extension (needed per session)
            self.conn.execute("LOAD delta")
            self.delta_enabled = True
            logger.info("Delta Lake extension enabled successfully")
        except Exception as e:
            logger.warning(f"Could not enable Delta extension: {e}. Delta operations will not be available.")
            self.delta_enabled = False

    def _init_model_views(self):
        """
        Auto-initialize v2.0 model views on connection startup.

        This checks if views exist and creates them if missing, ensuring:
        - Users don't need to manually run setup_duckdb_views.py
        - Views are available immediately on connection
        - Only runs for persistent databases (not :memory:)
        - Gracefully handles missing silver layer data
        - Recreates stale views that point to wrong storage paths
        - Validates views point to configured storage_path from run_config.json
        """
        try:
            # Get configured storage_path from run_config.json for validation
            from de_funk.utils.repo import get_repo_root
            import json

            repo_root = get_repo_root()
            configured_storage_root = None
            run_config_path = repo_root / 'configs' / 'pipelines' / 'run_config.json'
            if run_config_path.exists():
                with open(run_config_path) as f:
                    run_config = json.load(f)
                storage_path_str = run_config.get('defaults', {}).get('storage_path')
                if storage_path_str and Path(storage_path_str).exists():
                    configured_storage_root = Path(storage_path_str)
                    logger.debug(f"Configured storage_path: {configured_storage_root}")

            # Check if any v2.0 model schemas exist (quick check to avoid unnecessary work)
            # Including 'bronze' schema for Bronze layer views
            # NOTE: Must include 'securities' for normalized v3.0 architecture
            existing_schemas = self.conn.execute("""
                SELECT schema_name
                FROM information_schema.schemata
                WHERE schema_name IN ('securities', 'stocks', 'options', 'company', 'temporal', 'geography', 'bronze')
            """).fetchall()

            views_need_refresh = False

            # Check if views point to configured storage_path
            # If they point to a different path (e.g., local storage vs /shared/storage), force refresh
            if configured_storage_root and existing_schemas:
                try:
                    # Get the definition of a known view to check its path
                    view_def = self.conn.execute("""
                        SELECT sql FROM duckdb_views()
                        WHERE schema_name = 'stocks' AND view_name = 'dim_stock'
                        LIMIT 1
                    """).fetchone()

                    if view_def and view_def[0]:
                        view_sql = view_def[0]
                        # Check if view path contains configured storage root
                        configured_path_str = str(configured_storage_root)
                        if configured_path_str not in view_sql:
                            logger.info(
                                f"Views point to wrong storage path (expected {configured_path_str}), "
                                f"will refresh to use configured storage"
                            )
                            views_need_refresh = True
                except Exception as e:
                    logger.debug(f"Could not check view paths: {e}")

            # If schemas exist with tables, verify views actually work
            # Test both dimension AND fact tables to ensure complete validation
            # Bronze schema is validated by checking if any bronze.* views exist
            # NOTE: Normalized architecture (v3.0) - prices are in securities.fact_security_prices
            validation_queries = {
                'securities': [
                    'SELECT 1 FROM securities.dim_security LIMIT 1',
                    'SELECT 1 FROM securities.fact_security_prices LIMIT 1',
                ],
                'stocks': [
                    'SELECT 1 FROM stocks.dim_stock LIMIT 1',
                ],
                'company': [
                    'SELECT 1 FROM company.dim_company LIMIT 1',
                ],
                'temporal': [
                    'SELECT 1 FROM temporal.dim_calendar LIMIT 1',
                ],
                # Bronze views are auto-discovered, just check schema has tables
                'bronze': [],
            }

            if existing_schemas:
                for schema_name in [s[0] for s in existing_schemas]:
                    tables = self.conn.execute(f"""
                        SELECT COUNT(*)
                        FROM information_schema.tables
                        WHERE table_schema = '{schema_name}'
                    """).fetchone()[0]

                    if tables > 0:
                        # Views exist - validate ALL critical views can read data
                        queries = validation_queries.get(schema_name, [])
                        for query in queries:
                            try:
                                self.conn.execute(query).fetchone()
                            except Exception as e:
                                # View exists but can't read data - needs refresh
                                logger.info(f"View in '{schema_name}' is stale ({e}), will refresh all views")
                                views_need_refresh = True
                                break

                        if views_need_refresh:
                            break

                        if queries:
                            logger.debug(f"Views in '{schema_name}' are valid ({len(queries)} checked)")

                if not views_need_refresh and existing_schemas:
                    logger.debug("All views valid, skipping initialization")
                    return

            # Views don't exist, are incomplete, or are stale - initialize them
            logger.info("Initializing v2.0 model views...")

            # Import here to avoid circular dependency
            from de_funk.utils.repo import get_repo_root
            from config import ConfigLoader
            import json

            # Get repo root and config
            repo_root = get_repo_root()
            loader = ConfigLoader(repo_root=repo_root)
            config = loader.load()

            # Get storage path from run_config.json
            storage_root = None
            run_config_path = repo_root / 'configs' / 'pipelines' / 'run_config.json'
            if run_config_path.exists():
                with open(run_config_path) as f:
                    run_config = json.load(f)
                storage_path_str = run_config.get('defaults', {}).get('storage_path')
                if storage_path_str:
                    storage_root = Path(storage_path_str)
                    logger.debug(f"Using storage_path from run_config.json: {storage_root}")

            # Import and run view setup (but silently - don't spam logs)
            import sys
            from io import StringIO
            from scripts.setup.setup_duckdb_views import DuckDBViewSetup

            # Capture output to avoid spamming console
            old_stdout = sys.stdout
            sys.stdout = StringIO()

            try:
                setup = DuckDBViewSetup(db_path=Path(self.db_path), config=config, repo_root=repo_root, storage_root=storage_root)
                setup.setup_all(dry_run=False)
                logger.info("✓ Model views initialized successfully")
            finally:
                sys.stdout = old_stdout

        except Exception as e:
            # Don't fail connection if view setup fails - just log warning
            logger.warning(f"Could not auto-initialize model views: {e}")
            logger.info("Views can be manually created with: python -m scripts.setup.setup_duckdb_views")

    def _is_delta_table(self, path: str) -> bool:
        """
        Check if a path points to a Delta Lake table.

        Delta tables have a _delta_log directory containing transaction logs.

        Args:
            path: Path to check

        Returns:
            True if path is a Delta table, False otherwise
        """
        path_obj = Path(path)
        if not path_obj.exists():
            return False

        # Check for _delta_log directory (signature of Delta table)
        delta_log = path_obj / "_delta_log"
        return delta_log.exists() and delta_log.is_dir()

    def table(self, view_name: str) -> Any:
        """
        Get a table or view by name from the DuckDB catalog.

        This method allows sessions to use pre-created views
        instead of building tables from Bronze on every request.

        Args:
            view_name: Fully qualified view name (e.g., 'stocks.dim_stock')

        Returns:
            DuckDB relation for the view

        Raises:
            Exception: If view doesn't exist

        Example:
            df = conn.table('stocks.dim_stock')
            df = conn.table('securities.fact_security_prices')
        """
        # Use sql() to get a relation object with .filter(), .df() methods
        return self.conn.sql(f"SELECT * FROM {view_name}")

    def has_view(self, view_name: str) -> bool:
        """
        Check if a view exists in the database.

        Args:
            view_name: Fully qualified view name (e.g., 'stocks.dim_stock')

        Returns:
            True if view exists, False otherwise
        """
        try:
            # Parse schema.table format
            if '.' in view_name:
                schema, table = view_name.split('.', 1)
            else:
                schema = 'main'
                table = view_name

            result = self.conn.execute(f"""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema = '{schema}' AND table_name = '{table}'
            """).fetchone()
            return result[0] > 0
        except Exception:
            return False

    def read_table(self, path: str, format: str = "parquet", version: Optional[int] = None, timestamp: Optional[str] = None) -> Any:
        """
        Read a table from storage (Parquet or Delta Lake).

        DuckDB can query files directly without loading into memory!

        Args:
            path: Path to the table (file or directory)
            format: Format of the data ('parquet' or 'delta')
            version: For Delta tables, specific version to read (time travel)
            timestamp: For Delta tables, timestamp to read (time travel)

        Returns:
            DuckDB relation (lazy query result)

        Example:
            # Read current version
            df = conn.read_table('/path/to/delta', format='delta')

            # Read specific version (time travel)
            df = conn.read_table('/path/to/delta', format='delta', version=5)

            # Read at timestamp
            df = conn.read_table('/path/to/delta', format='delta', timestamp='2024-01-15 10:00:00')
        """
        path_obj = Path(path)

        # Auto-detect Delta tables
        if format == "parquet" and self._is_delta_table(path):
            logger.info(f"Auto-detected Delta table at {path}, switching to delta format")
            format = "delta"

        if format == "delta":
            if not self.delta_enabled:
                raise ValueError(
                    "Delta format requested but Delta extension is not enabled. "
                    "Install delta-rs: pip install deltalake"
                )
            return self._read_delta_table(path, version=version, timestamp=timestamp)

        elif format == "parquet":
            # DuckDB can query Parquet files directly
            # This is lazy - no data loaded until needed
            if path_obj.is_dir():
                # Read all parquet files in directory
                pattern = f"{path}/**/*.parquet"
                # Use from_parquet to get a relation object
                # hive_partitioning=True enables reading partition columns (e.g., asset_type=stocks)
                return self.conn.from_parquet(pattern, union_by_name=True, hive_partitioning=True)
            else:
                # Read single file
                return self.conn.from_parquet(path)

        else:
            raise ValueError(f"Unsupported format: {format}. Use 'parquet' or 'delta'")

    def _read_delta_table(self, path: str, version: Optional[int] = None, timestamp: Optional[str] = None) -> Any:
        """
        Read a Delta Lake table using DuckDB's delta_scan function.

        Args:
            path: Path to Delta table
            version: Specific version to read (time travel)
            timestamp: Timestamp to read (time travel)

        Returns:
            DuckDB relation
        """
        # DuckDB's delta_scan doesn't support time travel directly
        # For time travel, use delta-rs library to load specific version then scan with DuckDB
        if version is not None or timestamp is not None:
            try:
                from deltalake import DeltaTable

                # Load specific version using delta-rs
                if version is not None:
                    dt = DeltaTable(path, version=version)
                else:
                    dt = DeltaTable(path)  # timestamp-based loading not directly supported

                # Convert to pandas and then to DuckDB relation
                import pyarrow as pa
                arrow_table = dt.to_pyarrow_table()
                return self.conn.from_arrow(arrow_table)
            except ImportError:
                raise ImportError("Time travel requires 'deltalake' package: pip install deltalake")

        # For current version, use DuckDB's delta_scan (faster)
        # Use conn.sql() instead of conn.execute() to get a DuckDB relation
        # that supports .filter(), .df(), etc. methods
        query = f"SELECT * FROM delta_scan('{path}')"
        return self.conn.sql(query)

    def write_delta_table(
        self,
        df: pd.DataFrame,
        path: str,
        mode: str = "overwrite",
        partition_by: Optional[List[str]] = None,
        **kwargs
    ):
        """
        Write DataFrame to Delta Lake table.

        Args:
            df: Pandas DataFrame to write
            path: Path to Delta table
            mode: Write mode ('overwrite', 'append', 'merge')
            partition_by: Columns to partition by
            **kwargs: Additional arguments passed to write_deltalake

        Example:
            # Overwrite table
            conn.write_delta_table(df, '/path/to/delta', mode='overwrite')

            # Append to table
            conn.write_delta_table(df, '/path/to/delta', mode='append')

            # Partition by column
            conn.write_delta_table(df, '/path/to/delta', partition_by=['year', 'month'])
        """
        if not DELTA_AVAILABLE:
            raise ImportError(
                "Delta operations require deltalake package. "
                "Install it with: pip install deltalake"
            )

        if mode == "overwrite":
            write_deltalake(
                path,
                df,
                mode="overwrite",
                partition_by=partition_by,
                **kwargs
            )
        elif mode == "append":
            write_deltalake(
                path,
                df,
                mode="append",
                partition_by=partition_by,
                **kwargs
            )
        elif mode == "merge":
            # For merge, we need merge keys
            merge_keys = kwargs.pop('merge_keys', None)
            if not merge_keys:
                raise ValueError("merge mode requires 'merge_keys' parameter")
            self._merge_delta_table(df, path, merge_keys)
        else:
            raise ValueError(f"Unsupported mode: {mode}. Use 'overwrite', 'append', or 'merge'")

        logger.info(f"Wrote {len(df)} rows to Delta table at {path} (mode={mode})")

    def _merge_delta_table(self, df: pd.DataFrame, path: str, merge_keys: List[str]):
        """
        Merge (upsert) DataFrame into Delta table.

        Args:
            df: DataFrame with new/updated data
            path: Path to Delta table
            merge_keys: Columns to match on (e.g., ['ticker', 'trade_date'])
        """
        if not DELTA_AVAILABLE:
            raise ImportError("Merge requires deltalake package")

        dt = DeltaTable(path)

        # Build predicate for merge
        predicates = " AND ".join([f"target.{key} = source.{key}" for key in merge_keys])

        # Perform merge
        (
            dt.merge(
                source=df,
                predicate=predicates,
                source_alias="source",
                target_alias="target",
            )
            .when_matched_update_all()
            .when_not_matched_insert_all()
            .execute()
        )

        logger.info(f"Merged {len(df)} rows into Delta table at {path}")

    def get_delta_table_history(self, path: str) -> pd.DataFrame:
        """
        Get the version history of a Delta table.

        Args:
            path: Path to Delta table

        Returns:
            DataFrame with version history (version, timestamp, operation, etc.)

        Example:
            history = conn.get_delta_table_history('/path/to/delta')
            print(history[['version', 'timestamp', 'operation']])
        """
        if not DELTA_AVAILABLE:
            raise ImportError("Delta history requires deltalake package")

        dt = DeltaTable(path)
        history = dt.history()

        # Convert to DataFrame
        return pd.DataFrame(history)

    def optimize_delta_table(self, path: str, zorder_by: Optional[List[str]] = None):
        """
        Optimize Delta table (compact small files, optionally z-order).

        Args:
            path: Path to Delta table
            zorder_by: Columns to z-order by (for better data skipping)

        Example:
            # Basic compaction
            conn.optimize_delta_table('/path/to/delta')

            # With z-ordering
            conn.optimize_delta_table('/path/to/delta', zorder_by=['ticker', 'trade_date'])
        """
        if not DELTA_AVAILABLE:
            raise ImportError("Delta optimize requires deltalake package")

        dt = DeltaTable(path)

        # Compact small files
        dt.optimize.compact()
        logger.info(f"Compacted Delta table at {path}")

        # Z-order if requested
        if zorder_by:
            dt.optimize.z_order(zorder_by)
            logger.info(f"Z-ordered Delta table at {path} by {zorder_by}")

    def vacuum_delta_table(self, path: str, retention_hours: int = 168, enforce_retention: bool = True):
        """
        Vacuum Delta table (remove old files no longer needed).

        Args:
            path: Path to Delta table
            retention_hours: Retention period in hours (default: 168 = 7 days, minimum: 168)
            enforce_retention: Whether to enforce minimum retention period (default: True)

        Warning: Vacuuming removes old files and disables time travel to those versions!

        Example:
            # Vacuum files older than 7 days
            conn.vacuum_delta_table('/path/to/delta')

            # Custom retention (must be >= 168 hours unless enforce_retention=False)
            conn.vacuum_delta_table('/path/to/delta', retention_hours=24, enforce_retention=False)
        """
        if not DELTA_AVAILABLE:
            raise ImportError("Delta vacuum requires deltalake package")

        dt = DeltaTable(path)

        # Delta Lake enforces minimum 168 hours (7 days) retention by default
        # For testing, we can disable enforcement but it's risky for production
        dt.vacuum(
            retention_hours=retention_hours,
            enforce_retention_duration=enforce_retention,
            dry_run=False
        )
        logger.info(f"Vacuumed Delta table at {path} (retention={retention_hours}h, enforce={enforce_retention})")

    def read_parquet(self, path: str) -> Any:
        """
        Read parquet file(s) from path.

        Alias for read_table() for compatibility with models that call read_parquet().

        Args:
            path: Path to parquet file or directory

        Returns:
            DuckDB relation (lazy query result)
        """
        return self.read_table(path, format="parquet")

    def createDataFrame(self, data: list, schema=None) -> Any:
        """
        Create a DuckDB relation from data and schema.

        Compatibility method for Spark's createDataFrame API.
        This is primarily used for creating empty tables when no data exists.

        Args:
            data: List of rows (typically empty [])
            schema: PySpark StructType schema (optional)

        Returns:
            DuckDB relation
        """
        # If no schema provided, create empty relation with a placeholder column
        # (DuckDB requires at least one column in a DataFrame)
        if schema is None:
            return self.conn.from_df(pd.DataFrame({'_empty': pd.Series([], dtype='object')}))

        # Parse PySpark schema to create pandas DataFrame with correct types
        try:
            # Import PySpark types if available
            from pyspark.sql.types import StructType, StructField, StringType, IntegerType, LongType, DoubleType, BooleanType, TimestampType, DateType

            if isinstance(schema, StructType):
                # Map PySpark types to pandas/DuckDB types
                type_map = {
                    'StringType': 'object',
                    'IntegerType': 'int64',
                    'LongType': 'int64',
                    'DoubleType': 'float64',
                    'FloatType': 'float64',
                    'BooleanType': 'bool',
                    'TimestampType': 'datetime64[ns]',
                    'DateType': 'datetime64[ns]',
                }

                # Create empty pandas DataFrame with correct column types
                columns = {}
                for field in schema.fields:
                    field_type = field.dataType.__class__.__name__
                    pandas_type = type_map.get(field_type, 'object')
                    columns[field.name] = pd.Series([], dtype=pandas_type)

                df = pd.DataFrame(columns)
                return self.conn.from_df(df)
            else:
                # Schema is not StructType, create empty DataFrame with placeholder
                return self.conn.from_df(pd.DataFrame({'_empty': pd.Series([], dtype='object')}))

        except ImportError:
            # PySpark not available, create empty DataFrame with placeholder
            return self.conn.from_df(pd.DataFrame({'_empty': pd.Series([], dtype='object')}))
        except Exception as e:
            # Fallback: create empty DataFrame with placeholder
            logger.warning(f"Could not parse schema for createDataFrame: {e}")
            return self.conn.from_df(pd.DataFrame({'_empty': pd.Series([], dtype='object')}))

    def apply_filters(self, df: Any, filters: Dict[str, Any]) -> Any:
        """
        Apply filters to a DuckDB relation.

        Args:
            df: DuckDB relation
            filters: Dictionary of column -> filter value

        Returns:
            Filtered DuckDB relation
        """
        if not filters:
            return df

        # Get available columns from the relation
        try:
            available_cols = set(df.columns)
        except:
            available_cols = set()

        # Universal date columns that might trigger period overlap
        UNIVERSAL_DATE_COLUMNS = {'date', 'trade_date', 'forecast_date', 'fiscal_date',
                                  'report_date', 'effective_date', 'as_of_date'}

        # Build WHERE clause
        conditions = []
        for column, value in filters.items():
            if isinstance(value, dict):
                # Date range filter (start/end)
                if 'start' in value and 'end' in value:
                    start = value['start']
                    end = value['end']
                    # Convert datetime objects to strings
                    if hasattr(start, 'strftime'):
                        start = start.strftime('%Y-%m-%d')
                    if hasattr(end, 'strftime'):
                        end = end.strftime('%Y-%m-%d')

                    # Check if this is a period overlap case
                    # This happens when filtering by a date column that doesn't exist in the table,
                    # but the table has period_start_date_id and period_end_date_id
                    is_period_overlap = (
                        column in UNIVERSAL_DATE_COLUMNS and
                        'period_start_date_id' in available_cols and
                        'period_end_date_id' in available_cols and
                        column not in available_cols  # Column doesn't exist, so use period overlap
                    )

                    logger.debug(f"apply_filters: column={column}, available_cols={available_cols}, is_period_overlap={is_period_overlap}")

                    if is_period_overlap:
                        # Use temporal.dim_calendar to convert the filter dates to date_ids
                        # Then apply period overlap logic using those date_ids
                        # This requires a subquery to join with temporal.dim_calendar
                        conditions.append(
                            f"""(period_start_date_id <= (
                                SELECT date_id FROM temporal.dim_calendar WHERE date = '{end}' LIMIT 1
                            ) AND period_end_date_id >= (
                                SELECT date_id FROM temporal.dim_calendar WHERE date = '{start}' LIMIT 1
                            ))"""
                        )
                    else:
                        conditions.append(
                            f"{column} BETWEEN '{start}' AND '{end}'"
                        )
                # Numeric range filter (min/max)
                elif 'min' in value or 'max' in value:
                    if 'min' in value and value['min'] is not None and value['min'] > 0:
                        conditions.append(f"{column} >= {value['min']}")
                    if 'max' in value and value['max'] is not None:
                        conditions.append(f"{column} <= {value['max']}")
            elif isinstance(value, list):
                # IN filter
                if value:  # Only add if list is not empty
                    values_str = ", ".join(f"'{v}'" for v in value)
                    conditions.append(f"{column} IN ({values_str})")
            elif value is not None:
                # Equality filter (skip None values)
                if isinstance(value, str):
                    conditions.append(f"{column} = '{value}'")
                else:
                    conditions.append(f"{column} = {value}")

        if conditions:
            where_clause = " AND ".join(conditions)
            # Use DuckDB relation's filter method
            return df.filter(where_clause)

        return df

    def to_pandas(self, df: Any) -> pd.DataFrame:
        """
        Convert DuckDB relation to pandas DataFrame.

        Args:
            df: DuckDB relation, pandas DataFrame, or QueryResult

        Returns:
            Pandas DataFrame
        """
        import pandas as pd

        # Check if already pandas DataFrame
        if isinstance(df, pd.DataFrame):
            return df

        # Handle QueryResult wrapper (from measure execution)
        if hasattr(df, 'data'):
            df = df.data
            # Check if data is already pandas
            if isinstance(df, pd.DataFrame):
                return df

        # DuckDB relation has direct pandas conversion
        return df.df()

    def count(self, df: Any) -> int:
        """
        Get row count from DuckDB relation.

        Args:
            df: DuckDB relation

        Returns:
            Number of rows
        """
        # DuckDB relation has count() method
        return df.count('*').fetchone()[0]

    def cache(self, df: Any, name: Optional[str] = None) -> Any:
        """
        Cache a DuckDB relation.

        Args:
            df: DuckDB relation to cache
            name: Optional name for the cached table

        Returns:
            Cached relation
        """
        # Generate a name if not provided
        if not name:
            name = f"_cached_{id(df)}"

        # Create a temporary table from the relation
        df.create(name)
        self._cached_tables[name] = df
        return self.conn.table(name)

    def uncache(self, df: Any):
        """
        Remove cached table.

        Args:
            df: DuckDB relation to uncache
        """
        # Find the name associated with this dataframe
        name_to_remove = None
        for name, cached_df in self._cached_tables.items():
            if cached_df is df:
                name_to_remove = name
                break

        if name_to_remove:
            self.conn.execute(f"DROP TABLE IF EXISTS {name_to_remove}")
            del self._cached_tables[name_to_remove]

    def stop(self):
        """Close the DuckDB connection."""
        # Clear cached tables (only if initialized)
        if hasattr(self, '_cached_tables') and hasattr(self, 'conn') and self.conn:
            for name in list(self._cached_tables.keys()):
                self.conn.execute(f"DROP TABLE IF EXISTS {name}")
            self._cached_tables.clear()

        # Close connection
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
            self.conn = None

    def execute_sql(self, query: str) -> Any:
        """
        Execute raw SQL query.

        Args:
            query: SQL query string

        Returns:
            DuckDB relation with results
        """
        return self.conn.execute(query)

    def execute(self, query: str) -> Any:
        """
        Execute raw SQL query (alias for execute_sql).

        Provided for compatibility with code expecting execute() method.

        Args:
            query: SQL query string

        Returns:
            DuckDB relation with results
        """
        return self.execute_sql(query)

    # NOTE: table() method is defined earlier in this file (around line 180)
    # It uses SQL query to properly support schema.table format like 'stocks.dim_stock'

    def __del__(self):
        """Cleanup on deletion."""
        try:
            self.stop()
        except Exception:
            # Silently handle cleanup errors (object may be partially initialized)
            pass
