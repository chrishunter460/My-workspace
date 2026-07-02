"""
SparkNormalizer - Standard data normalization utilities for all providers.

Provides a unified, pure-Spark normalization pipeline that handles:
- Field renaming (source → target from endpoint schema)
- Type coercion (using TRY_CAST for safe conversion)
- Date parsing
- Computed fields
- Metadata columns (ingestion_timestamp, snapshot_date)
- Final column selection and ordering

Usage:
    from de_funk.pipelines.base.normalizer import SparkNormalizer

    normalizer = SparkNormalizer(spark)

    # From records list
    df = normalizer.normalize(
        records,
        field_mappings={'OldName': 'new_name'},
        type_coercions={'amount': 'double', 'count': 'long'},
        date_columns=['trade_date', 'fiscal_date'],
        add_metadata=True
    )

    # Or use endpoint schema directly
    df = normalizer.normalize_with_schema(records, endpoint_schema)

Author: de_Funk Team
Date: January 2026
"""
from __future__ import annotations

from typing import Dict, List, Optional, Any
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, LongType, StringType, DateType, TimestampType

from de_funk.config.logging import get_logger

logger = get_logger(__name__)


class SparkNormalizer:
    """
    Standard Spark-based data normalizer for all providers.

    Uses pure Spark operations (no pandas) for:
    - Consistent type handling
    - Memory efficiency on large datasets
    - Proper null handling via TRY_CAST
    """

    def __init__(self, spark: SparkSession):
        """
        Initialize normalizer with Spark session.

        Args:
            spark: Active SparkSession
        """
        self.spark = spark

    def normalize(
        self,
        records: List[Dict],
        field_mappings: Optional[Dict[str, str]] = None,
        type_coercions: Optional[Dict[str, str]] = None,
        date_columns: Optional[List[str]] = None,
        timestamp_columns: Optional[List[str]] = None,
        computed_columns: Optional[Dict[str, str]] = None,
        add_metadata: bool = True,
        final_columns: Optional[List[str]] = None,
        metadata_columns: Optional[Dict[str, Any]] = None
    ) -> DataFrame:
        """
        Normalize raw records to a Spark DataFrame.

        Args:
            records: List of raw record dictionaries
            field_mappings: Dict of source_name → target_name for column renames
            type_coercions: Dict of column_name → type ('double', 'long', 'string')
            date_columns: List of columns to parse as dates
            timestamp_columns: List of columns to parse as timestamps
            computed_columns: Dict of column_name → Spark SQL expression
            add_metadata: If True, add ingestion_timestamp and snapshot_date
            final_columns: If provided, select only these columns in this order
            metadata_columns: Additional metadata columns to add (name → value)

        Returns:
            Normalized Spark DataFrame
        """
        if not records:
            return self.spark.createDataFrame([], samplingRatio=1.0)

        # Step 1: Create DataFrame directly from records
        df = self.spark.createDataFrame(records)
        logger.debug(f"Created DataFrame with {df.count()} rows, columns: {df.columns[:10]}")

        # Step 2: Apply field mappings (rename columns)
        if field_mappings:
            df = self._apply_field_mappings(df, field_mappings)

        # Step 3: Apply type coercions
        if type_coercions:
            df = self._apply_type_coercions(df, type_coercions)

        # Step 4: Parse date columns
        if date_columns:
            df = self._parse_dates(df, date_columns)

        # Step 5: Parse timestamp columns
        if timestamp_columns:
            df = self._parse_timestamps(df, timestamp_columns)

        # Step 6: Apply computed columns
        if computed_columns:
            df = self._apply_computed_columns(df, computed_columns)

        # Step 7: Add metadata columns
        if add_metadata:
            df = self._add_metadata(df, metadata_columns)

        # Step 8: Select final columns
        if final_columns:
            df = self._select_final_columns(df, final_columns)

        return df

    def normalize_with_schema(
        self,
        records: List[Dict],
        schema_fields: List[Dict[str, Any]],
        add_metadata: bool = True
    ) -> DataFrame:
        """
        Normalize using endpoint schema field definitions.

        Args:
            records: List of raw record dictionaries
            schema_fields: List of field dicts with 'name', 'source', 'type', 'coerce'
            add_metadata: If True, add metadata columns

        Returns:
            Normalized Spark DataFrame
        """
        # Extract mappings from schema
        field_mappings = {}
        type_coercions = {}
        date_columns = []
        timestamp_columns = []
        final_columns = []

        for field in schema_fields:
            name = field.get('name')
            source = field.get('source')
            field_type = field.get('type', 'string').lower()
            coerce_type = field.get('coerce')

            # Field mapping
            if source and source not in ('_computed', '_generated', '_na'):
                field_mappings[source] = name

            # Type coercion
            if coerce_type:
                type_coercions[name] = coerce_type
            elif field_type in ('double', 'float', 'long', 'int', 'integer', 'bigint'):
                type_coercions[name] = field_type

            # Date/timestamp detection
            if field_type == 'date':
                date_columns.append(name)
            elif field_type == 'timestamp':
                timestamp_columns.append(name)

            final_columns.append(name)

        return self.normalize(
            records,
            field_mappings=field_mappings,
            type_coercions=type_coercions,
            date_columns=date_columns if date_columns else None,
            timestamp_columns=timestamp_columns if timestamp_columns else None,
            add_metadata=add_metadata,
            final_columns=final_columns if final_columns else None
        )

    # =========================================================================
    # INTERNAL METHODS
    # =========================================================================

    def _apply_field_mappings(
        self,
        df: DataFrame,
        field_mappings: Dict[str, str]
    ) -> DataFrame:
        """Rename columns based on field mappings."""
        df_columns = df.columns
        rename_count = 0

        for source, target in field_mappings.items():
            if source in df_columns and source != target:
                df = df.withColumnRenamed(source, target)
                rename_count += 1

        if rename_count > 0:
            logger.debug(f"Renamed {rename_count} columns")

        return df

    def _apply_type_coercions(
        self,
        df: DataFrame,
        type_coercions: Dict[str, str]
    ) -> DataFrame:
        """
        Apply type coercions using TRY_CAST for safe conversion.

        TRY_CAST returns NULL for invalid values instead of failing.
        All numeric types are cast to DoubleType for consistency
        (avoids NaN → BIGINT overflow issues).

        Uses try_cast() to handle malformed values like 'None' strings -
        returns NULL instead of failing.
        """
        df_columns = df.columns
        coerced_count = 0

        for column, target_type in type_coercions.items():
            if column not in df_columns:
                continue

            target_type_lower = target_type.lower()

            # Use try_cast for safe conversion - returns NULL for malformed values
            # (e.g., Alpha Vantage returns literal "None" strings)
            if target_type_lower in ('double', 'float', 'decimal'):
                df = df.withColumn(column, F.col(column).try_cast(DoubleType()))
                coerced_count += 1
            elif target_type_lower in ('long', 'bigint', 'int', 'integer'):
                # Cast to double for NaN safety (keeps as double, not long)
                df = df.withColumn(column, F.col(column).try_cast(DoubleType()))
                coerced_count += 1
            elif target_type_lower == 'string':
                df = df.withColumn(column, F.col(column).cast(StringType()))
                coerced_count += 1

        if coerced_count > 0:
            logger.debug(f"Coerced {coerced_count} columns to target types")

        return df

    def _parse_dates(self, df: DataFrame, date_columns: List[str]) -> DataFrame:
        """Parse string columns as dates. Handles invalid values as NULL.

        Invalid values include:
        - 'None' string (Alpha Vantage returns this instead of null)
        - '0000-00-00' (invalid placeholder date)
        - Empty strings
        """
        df_columns = df.columns

        for column in date_columns:
            if column in df_columns:
                # Replace invalid date values with null, then parse date
                df = df.withColumn(
                    column,
                    F.to_date(
                        F.when(
                            (F.col(column) == "None") |
                            (F.col(column) == "0000-00-00") |
                            (F.col(column) == ""),
                            None
                        ).otherwise(F.col(column))
                    )
                )

        return df

    def _parse_timestamps(self, df: DataFrame, timestamp_columns: List[str]) -> DataFrame:
        """Parse string columns as timestamps. Handles invalid values as NULL.

        Invalid values include:
        - 'None' string (Alpha Vantage returns this instead of null)
        - '0000-00-00' variants (invalid placeholder dates)
        - Empty strings
        """
        df_columns = df.columns

        for column in timestamp_columns:
            if column in df_columns:
                # Replace invalid timestamp values with null, then parse timestamp
                df = df.withColumn(
                    column,
                    F.to_timestamp(
                        F.when(
                            (F.col(column) == "None") |
                            (F.col(column).startswith("0000-00-00")) |
                            (F.col(column) == ""),
                            None
                        ).otherwise(F.col(column))
                    )
                )

        return df

    def _apply_computed_columns(
        self,
        df: DataFrame,
        computed_columns: Dict[str, str]
    ) -> DataFrame:
        """Apply computed columns using Spark SQL expressions."""
        for column, expression in computed_columns.items():
            try:
                df = df.withColumn(column, F.expr(expression))
            except Exception as e:
                logger.warning(f"Failed to compute column {column}: {e}")
                df = df.withColumn(column, F.lit(None))

        return df

    def _add_metadata(
        self,
        df: DataFrame,
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> DataFrame:
        """Add standard metadata columns."""
        df = (df
              .withColumn('ingestion_timestamp', F.current_timestamp())
              .withColumn('snapshot_date', F.current_date()))

        # Add any extra metadata columns
        if extra_metadata:
            for name, value in extra_metadata.items():
                df = df.withColumn(name, F.lit(value))

        return df

    def _select_final_columns(
        self,
        df: DataFrame,
        final_columns: List[str]
    ) -> DataFrame:
        """Select final columns, adding missing ones as NULL."""
        df_columns = df.columns

        for column in final_columns:
            if column not in df_columns:
                df = df.withColumn(column, F.lit(None))

        return df.select(*final_columns)


# Convenience function for one-off normalization
def normalize_records(
    spark: SparkSession,
    records: List[Dict],
    **kwargs
) -> DataFrame:
    """
    Convenience function for normalizing records.

    Args:
        spark: SparkSession
        records: List of record dicts
        **kwargs: Passed to SparkNormalizer.normalize()

    Returns:
        Normalized DataFrame
    """
    normalizer = SparkNormalizer(spark)
    return normalizer.normalize(records, **kwargs)
