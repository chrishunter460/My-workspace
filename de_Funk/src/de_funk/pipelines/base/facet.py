"""
Base Facet class for data transformation pipelines.

Facets transform raw API responses into normalized Spark DataFrames.
This is the foundation for all provider-specific facets.

v2.8: Unified markdown-driven architecture
    - Schema, coercion rules, field mappings all come from endpoint markdown
    - Provider-agnostic: works for Alpha Vantage, Chicago, Cook County, etc.
    - Subclasses only need to add provider-specific cleaning (optional)

Usage:
    # Direct instantiation with endpoint config
    facet = Facet(spark, provider_id="alpha_vantage", endpoint_id="balance_sheet")
    df = facet.normalize(raw_data)

    # Or subclass for provider-specific behavior
    class AlphaVantageFacet(Facet):
        def _clean_raw_value(self, value):
            # Handle AV-specific "None" strings
            if value == "None":
                return None
            return value

Author: de_Funk Team
Date: December 2025
Updated: January 2026 - Unified markdown-driven architecture
"""
from __future__ import annotations

from typing import Dict, List, Iterable, Tuple, Optional, Any
from pyspark.sql import DataFrame, functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, IntegerType, LongType,
    BooleanType, DateType, TimestampType
)

from de_funk.config.logging import get_logger

logger = get_logger(__name__)


# ---------- Safe column helpers ----------

def coalesce_existing(df: DataFrame, candidates: Iterable[str]):
    """coalesce(...) but only over columns that actually exist."""
    cols = [F.col(c) for c in candidates if c in df.columns]
    return F.coalesce(*cols) if cols else F.lit(None)


def first_existing(df: DataFrame, candidates: Iterable[str]):
    """Return the first existing column as a Column, else NULL literal."""
    for c in candidates:
        if c in df.columns:
            return F.col(c)
    return F.lit(None)


def _type_from_str(t: str):
    t = (t or "").lower()
    return {
        "string": StringType(),
        "double": DoubleType(),
        "float": DoubleType(),
        "int": IntegerType(),
        "integer": IntegerType(),
        "long": LongType(),
        "bigint": LongType(),
        "boolean": BooleanType(),
        "date": DateType(),
        "timestamp": TimestampType(),
    }.get(t, StringType())


# ---------- Facet base ----------

class Facet:
    """
    Markdown-driven base class for data transformation facets.

    Configuration is loaded from endpoint markdown frontmatter:
    - schema: Field definitions with source mappings and {coerce: type}
    - facet_config: Response structure (arrays, fixed_fields)
    - computed_fields: Derived field expressions

    Features:
      1) Loads all config from endpoint markdown (single source of truth)
      2) Pre-coerces python dicts for numeric keys to stable types
      3) Unions batches with unionByName
      4) Applies computed fields from markdown expressions
      5) Enforces final Spark casts and column order from schema

    Class Attributes (legacy - prefer markdown):
        NUMERIC_COERCE: Dict mapping field names to target types for pre-coercion
        SPARK_CASTS: Dict mapping column names to Spark type strings for final casting
        FINAL_COLUMNS: Optional list of (name, type) tuples defining final schema

    Instance Attributes:
        provider_id: Provider identifier (e.g., "alpha_vantage", "chicago")
        endpoint_id: Endpoint identifier (e.g., "balance_sheet", "budget")
    """

    # Legacy class attributes (prefer markdown config)
    NUMERIC_COERCE: Dict[str, str] = {}
    SPARK_CASTS: Dict[str, str] = {}
    FINAL_COLUMNS: Optional[List[Tuple[str, str]]] = None

    # Set in subclass or pass to constructor
    PROVIDER_ID: Optional[str] = None
    ENDPOINT_ID: Optional[str] = None

    def __init__(
        self,
        spark,
        provider_id: str = None,
        endpoint_id: str = None,
        **kwargs
    ):
        """
        Initialize facet with optional markdown configuration.

        Args:
            spark: SparkSession
            provider_id: Provider identifier (overrides class PROVIDER_ID)
            endpoint_id: Endpoint identifier (overrides class ENDPOINT_ID)
            **kwargs: Additional parameters passed to subclass
        """
        self.spark = spark
        self.provider_id = provider_id or self.PROVIDER_ID
        self.endpoint_id = endpoint_id or self.ENDPOINT_ID
        self._extra = kwargs

        # Cache for markdown schema
        self._md_schema_cache: Optional[Dict[str, Any]] = None

    # =========================================================================
    # MARKDOWN SCHEMA LOADING (unified across all providers)
    # =========================================================================

    def _load_markdown_schema(self) -> Dict[str, Any]:
        """
        Load and cache schema information from markdown endpoint file.

        Returns dict with:
            - schema: List of field dicts from markdown
            - coerce_rules: Dict[source_field, type] for pre-coercion
            - spark_casts: Dict[output_name, type] for Spark casts
            - final_columns: List[(output_name, type)]
            - field_mappings: Dict[source_field, output_name]
            - computed_fields: List of computed field definitions
            - facet_config: Response structure config (arrays, fixed_fields)
        """
        if self._md_schema_cache is not None:
            return self._md_schema_cache

        if not self.endpoint_id:
            self._md_schema_cache = {}
            return self._md_schema_cache

        try:
            from de_funk.config.markdown_loader import get_markdown_loader
            from de_funk.utils.repo import get_repo_root

            repo_root = get_repo_root()
            loader = get_markdown_loader(repo_root)

            # Get full endpoint config (includes facet_config)
            endpoint_config = loader.get_endpoint_config(self.endpoint_id)
            facet_config = endpoint_config.get('facet_config', {}) if endpoint_config else {}

            # Get schema fields
            schema = loader.get_endpoint_schema(self.endpoint_id)
            if not schema:
                self._md_schema_cache = {'facet_config': facet_config}
                return self._md_schema_cache

            # Derive coercion rules (source_field -> type) for pre-coercion
            coerce_rules = {}
            for f in schema:
                if f.get('coerce') and f.get('source') not in ('_computed', '_generated', '_param', '_key', '_na'):
                    coerce_rules[f['source']] = f['coerce']

            # Derive Spark casts (output_name -> type) for final casting
            spark_casts = {}
            for f in schema:
                if f.get('coerce'):
                    spark_casts[f['name']] = f['coerce']

            # Derive final columns (output_name, type)
            final_columns = [(f['name'], f['type']) for f in schema]

            # Derive field mappings (source -> output)
            field_mappings = {}
            for f in schema:
                src = f.get('source')
                if src and src not in ('_computed', '_generated', '_param', '_key', '_na'):
                    field_mappings[src] = f['name']

            # Get computed fields
            computed = []
            for f in schema:
                if f.get('source') == '_computed' and f.get('expr'):
                    computed.append({
                        'name': f['name'],
                        'type': f['type'],
                        'expr': f['expr'],
                        'default': f.get('default'),
                    })

            self._md_schema_cache = {
                'schema': schema,
                'coerce_rules': coerce_rules,
                'spark_casts': spark_casts,
                'final_columns': final_columns,
                'field_mappings': field_mappings,
                'computed_fields': computed,
                'facet_config': facet_config,
            }
            return self._md_schema_cache

        except Exception as e:
            logger.warning(f"Could not load markdown schema for {self.endpoint_id}: {e}")
            self._md_schema_cache = {}
            return self._md_schema_cache

    def get_coerce_rules(self) -> Dict[str, str]:
        """Get source field -> type coercion rules from markdown schema."""
        md_info = self._load_markdown_schema()
        return md_info.get('coerce_rules', {})

    def get_spark_casts(self) -> Dict[str, str]:
        """Get output_name -> type casts from markdown schema."""
        md_info = self._load_markdown_schema()
        return md_info.get('spark_casts', {})

    def get_final_columns(self) -> List[Tuple[str, str]]:
        """Get final columns list from markdown schema."""
        md_info = self._load_markdown_schema()
        return md_info.get('final_columns', [])

    def get_field_mappings(self) -> Dict[str, str]:
        """Get source -> output field name mappings from markdown schema."""
        md_info = self._load_markdown_schema()
        return md_info.get('field_mappings', {})

    def get_computed_fields(self) -> List[Dict[str, Any]]:
        """Get computed field definitions from markdown schema."""
        md_info = self._load_markdown_schema()
        return md_info.get('computed_fields', [])

    def get_facet_config(self) -> Dict[str, Any]:
        """Get facet configuration (response_arrays, fixed_fields, etc.)."""
        md_info = self._load_markdown_schema()
        return md_info.get('facet_config', {})

    # =========================================================================
    # DATA CLEANING (override in subclass for provider-specific behavior)
    # =========================================================================

    def _clean_raw_value(self, value: Any) -> Any:
        """
        Clean a single raw value from API response.

        Override in subclass for provider-specific cleaning:
        - Alpha Vantage: Handle "None" strings
        - Socrata: Handle date format variations

        Args:
            value: Raw value from API

        Returns:
            Cleaned value (or None if invalid)
        """
        if value is None:
            return None
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned in ("", "N/A", "-"):
                return None
            return cleaned
        return value

    def _clean_raw_row(self, row: dict) -> dict:
        """Clean all values in a raw data row."""
        return {k: self._clean_raw_value(v) for k, v in row.items()}

    def _clean_raw_batches(self, raw_batches: List[List[dict]]) -> List[dict]:
        """Clean and flatten raw batches into single list of rows."""
        rows = []
        for batch in raw_batches:
            for item in batch:
                if isinstance(item, dict):
                    rows.append(self._clean_raw_row(item))
                else:
                    rows.append(item)
        return rows

    # =========================================================================
    # TYPE COERCION
    # =========================================================================

    def _coerce_rows(self, rows: List[dict]) -> List[dict]:
        """
        Pre-coerce numeric fields in raw JSON rows so Spark sees a consistent schema.

        Uses coercion rules from markdown schema (or legacy NUMERIC_COERCE).
        """
        # Get coerce rules from markdown, fall back to class attribute
        coerce_rules = self.get_coerce_rules() or self.NUMERIC_COERCE

        if not rows or not coerce_rules:
            return rows

        out = []
        for r in rows:
            rr = dict(r)
            for k, typ in coerce_rules.items():
                if k not in rr or rr[k] is None:
                    continue
                val = rr[k]
                typ_lower = typ.lower()
                if typ_lower in ("double", "float", "decimal"):
                    if isinstance(val, int):
                        rr[k] = float(val)
                    elif isinstance(val, str):
                        try:
                            rr[k] = float(val)
                        except (ValueError, TypeError):
                            rr[k] = None
                elif typ_lower in ("long", "bigint", "int", "integer"):
                    if isinstance(val, float):
                        rr[k] = int(val)
                    elif isinstance(val, str):
                        try:
                            rr[k] = int(float(val))
                        except (ValueError, TypeError):
                            rr[k] = None
            out.append(rr)
        return out

    def _apply_spark_casts(self, df: DataFrame) -> DataFrame:
        """Apply Spark type casts from markdown schema."""
        # Get casts from markdown, fall back to class attribute
        spark_casts = self.get_spark_casts() or self.SPARK_CASTS

        if not spark_casts:
            return df

        for col_name, cast_type in spark_casts.items():
            if col_name in df.columns:
                # Use TRY_CAST for safe type conversion (returns NULL on failure)
                df = df.withColumn(col_name, F.expr(f"TRY_CAST(`{col_name}` AS {cast_type})"))
            else:
                df = df.withColumn(col_name, F.lit(None).cast(cast_type))

        return df

    def _apply_final_columns(self, df: DataFrame) -> DataFrame:
        """
        Ensure a stable column set and order from markdown schema.

        If FINAL_COLUMNS is provided (from markdown or class attribute),
        select those columns in order; any missing ones are created as NULL.
        """
        # Get final columns from markdown, fall back to class attribute
        final_columns = self.get_final_columns() or self.FINAL_COLUMNS

        if not final_columns:
            return df

        sel = []
        for name, t in final_columns:
            if name in df.columns:
                sel.append(F.col(name).cast(t).alias(name))
            else:
                sel.append(F.lit(None).cast(t).alias(name))
        return df.select(*sel)

    def _apply_computed_fields(self, df: DataFrame) -> DataFrame:
        """Apply computed fields from markdown schema expressions."""
        computed_fields = self.get_computed_fields()

        for field in computed_fields:
            name = field['name']
            expr = field.get('expr')
            if expr and name not in df.columns:
                try:
                    df = df.withColumn(name, F.expr(expr))
                except Exception as e:
                    logger.warning(f"Failed to compute field {name}: {e}")
                    field_type = field.get('type', 'double')
                    default = field.get('default')
                    if default is not None:
                        df = df.withColumn(name, F.lit(default).cast(field_type))
                    else:
                        df = df.withColumn(name, F.lit(None).cast(field_type))

        return df

    # =========================================================================
    # MAIN NORMALIZATION PIPELINE
    # =========================================================================

    def _empty_df(self) -> DataFrame:
        """
        Produce an empty DataFrame matching schema from markdown.
        """
        final_columns = self.get_final_columns() or self.FINAL_COLUMNS

        if final_columns:
            fields = [StructField(name, _type_from_str(t), True) for name, t in final_columns]
            schema = StructType(fields)
            return self.spark.createDataFrame([], schema)

        return self.spark.createDataFrame(self.spark.sparkContext.emptyRDD(), StructType([]))

    def normalize(self, raw_batches: List[List[dict]]) -> DataFrame:
        """
        Main normalization pipeline.

        Steps:
        1. Clean raw data (provider-specific via _clean_raw_value)
        2. Pre-coerce types (from markdown coerce_rules)
        3. Create DataFrame
        4. Apply postprocess (subclass hook)
        5. Apply computed fields (from markdown)
        6. Apply Spark casts (from markdown)
        7. Apply final column order (from markdown)

        Args:
            raw_batches: List of lists of dicts (batches of API responses)

        Returns:
            Spark DataFrame with normalized data
        """
        # Step 1: Clean raw data
        rows = self._clean_raw_batches(raw_batches)

        if not rows:
            return self._empty_df()

        # Step 2: Pre-coerce types
        rows = self._coerce_rows(rows)

        # Step 3: Create DataFrame
        df = self.spark.createDataFrame(rows, samplingRatio=1.0)

        # Step 4: Apply postprocess (subclass hook)
        df = self.postprocess(df)

        # Step 5: Apply computed fields
        df = self._apply_computed_fields(df)

        # Step 6: Apply Spark casts
        df = self._apply_spark_casts(df)

        # Step 7: Apply final columns
        df = self._apply_final_columns(df)

        return df

    def postprocess(self, df: DataFrame) -> DataFrame:
        """
        Override in child class to apply custom transformations.

        Args:
            df: Input DataFrame after batch union

        Returns:
            Transformed DataFrame
        """
        return df

    def validate(self, df: DataFrame) -> DataFrame:
        """
        Override in child class to validate output DataFrame.

        Args:
            df: Output DataFrame to validate

        Returns:
            DataFrame (same as input, for chaining)

        Raises:
            ValueError: If validation fails
        """
        return df

    def calls(self):
        """
        Override in child class to generate API call specifications.

        Yields:
            Dict with keys like 'ep_name', 'params' for API calls
        """
        raise NotImplementedError("Child facet must implement calls()")
