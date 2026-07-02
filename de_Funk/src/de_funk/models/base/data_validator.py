"""
DataValidator - Base class for data validation in model builders.

Provides reusable validation patterns for checking:
- Required columns existence
- Data types and ranges
- Data quality metrics (nulls, outliers, coverage)
- Time series continuity

Usage:
    class MyValidator(DataValidator):
        def get_required_columns(self):
            return ['ticker', 'date', 'close']

    validator = MyValidator(spark_or_pandas_df)
    report = validator.validate()
    if not report.is_valid:
        print(report.summary())
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class ValidationIssue:
    """Single validation issue."""
    level: str  # 'error', 'warning', 'info'
    category: str  # 'column', 'type', 'range', 'quality', 'coverage'
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

    def __str__(self):
        return f"[{self.level.upper()}] {self.category}: {self.message}"


@dataclass
class ValidationReport:
    """Complete validation report."""
    validator_name: str
    timestamp: datetime = field(default_factory=datetime.now)
    issues: List[ValidationIssue] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        """True if no errors (warnings are OK)."""
        return not any(i.level == 'error' for i in self.issues)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.level == 'error')

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.level == 'warning')

    def add_error(self, category: str, message: str, **details):
        """Add an error issue."""
        self.issues.append(ValidationIssue('error', category, message, details))

    def add_warning(self, category: str, message: str, **details):
        """Add a warning issue."""
        self.issues.append(ValidationIssue('warning', category, message, details))

    def add_info(self, category: str, message: str, **details):
        """Add an info issue."""
        self.issues.append(ValidationIssue('info', category, message, details))

    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            f"Validation Report: {self.validator_name}",
            f"  Timestamp: {self.timestamp.isoformat()}",
            f"  Status: {'VALID' if self.is_valid else 'INVALID'}",
            f"  Errors: {self.error_count}, Warnings: {self.warning_count}",
        ]

        if self.metrics:
            lines.append("  Metrics:")
            for key, value in self.metrics.items():
                lines.append(f"    {key}: {value}")

        if self.issues:
            lines.append("  Issues:")
            for issue in self.issues:
                lines.append(f"    {issue}")

        return "\n".join(lines)


class DataValidator(ABC):
    """
    Base class for data validation.

    Subclasses define what to validate by implementing abstract methods.
    The validate() method orchestrates all checks and returns a report.
    """

    def __init__(self, df: Any, backend: str = 'auto'):
        """
        Initialize validator with DataFrame.

        Args:
            df: Spark DataFrame or pandas DataFrame to validate
            backend: 'spark', 'pandas', or 'auto' (detect from df type)
        """
        self.df = df
        self.backend = self._detect_backend(df) if backend == 'auto' else backend
        self._columns: Optional[Set[str]] = None
        self._row_count: Optional[int] = None

    def _detect_backend(self, df: Any) -> str:
        """Detect if DataFrame is Spark or pandas."""
        type_name = type(df).__name__
        if 'DataFrame' in type_name and hasattr(df, 'rdd'):
            return 'spark'
        return 'pandas'

    @property
    def columns(self) -> Set[str]:
        """Get column names (cached)."""
        if self._columns is None:
            if self.backend == 'spark':
                self._columns = set(self.df.columns)
            else:
                self._columns = set(self.df.columns)
        return self._columns

    @property
    def row_count(self) -> int:
        """Get row count (cached)."""
        if self._row_count is None:
            if self.backend == 'spark':
                self._row_count = self.df.count()
            else:
                self._row_count = len(self.df)
        return self._row_count

    # ================================================================
    # ABSTRACT METHODS - Subclasses must implement
    # ================================================================

    @abstractmethod
    def get_required_columns(self) -> List[str]:
        """
        Return list of columns that MUST exist.

        Returns:
            List of column names
        """
        pass

    @abstractmethod
    def get_numeric_columns(self) -> List[str]:
        """
        Return list of columns that should be numeric.

        Returns:
            List of column names expected to be numeric
        """
        pass

    @abstractmethod
    def get_date_column(self) -> Optional[str]:
        """
        Return the date column name for time series validation.

        Returns:
            Column name or None if not a time series
        """
        pass

    @abstractmethod
    def get_entity_column(self) -> Optional[str]:
        """
        Return the entity column name (e.g., ticker, indicator_code).

        Returns:
            Column name or None if not entity-based
        """
        pass

    # ================================================================
    # OPTIONAL OVERRIDES - Subclasses can customize
    # ================================================================

    def get_optional_columns(self) -> List[str]:
        """Return columns that are nice to have but not required."""
        return []

    def get_valid_ranges(self) -> Dict[str, tuple]:
        """
        Return valid ranges for numeric columns.

        Returns:
            Dict mapping column name to (min, max) tuple.
            Use None for unbounded: (0, None) means >= 0
        """
        return {}

    def get_min_rows(self) -> int:
        """Minimum number of rows required."""
        return 1

    def get_null_thresholds(self) -> Dict[str, float]:
        """
        Return acceptable null percentage thresholds per column.

        Returns:
            Dict mapping column name to max allowed null percentage (0.0-1.0)
        """
        return {}

    # ================================================================
    # VALIDATION METHODS
    # ================================================================

    def validate(self) -> ValidationReport:
        """
        Run all validations and return report.

        Returns:
            ValidationReport with all issues and metrics
        """
        report = ValidationReport(validator_name=self.__class__.__name__)

        # Run validations in order
        self._validate_columns(report)
        self._validate_row_count(report)

        # Only proceed with data checks if we have required columns
        if report.is_valid:
            self._validate_data_types(report)
            self._validate_ranges(report)
            self._validate_nulls(report)
            self._validate_time_series(report)

        # Collect metrics
        self._collect_metrics(report)

        return report

    def _validate_columns(self, report: ValidationReport):
        """Check required and optional columns exist."""
        required = set(self.get_required_columns())
        optional = set(self.get_optional_columns())
        actual = self.columns

        # Check required
        missing_required = required - actual
        if missing_required:
            report.add_error(
                'column',
                f"Missing required columns: {sorted(missing_required)}",
                missing=list(missing_required),
                available=list(actual)
            )

        # Check optional (warning only)
        missing_optional = optional - actual
        if missing_optional:
            report.add_warning(
                'column',
                f"Missing optional columns: {sorted(missing_optional)}",
                missing=list(missing_optional)
            )

    def _validate_row_count(self, report: ValidationReport):
        """Check minimum row count."""
        min_rows = self.get_min_rows()
        actual_rows = self.row_count

        if actual_rows < min_rows:
            report.add_error(
                'coverage',
                f"Insufficient rows: {actual_rows} < {min_rows} required",
                actual=actual_rows,
                required=min_rows
            )
        elif actual_rows == 0:
            report.add_error('coverage', "DataFrame is empty")

    def _validate_data_types(self, report: ValidationReport):
        """Validate numeric columns are actually numeric."""
        numeric_cols = self.get_numeric_columns()

        for col in numeric_cols:
            if col not in self.columns:
                continue

            dtype = str(self.df.schema[col].dataType).lower()
            is_numeric = any(t in dtype for t in ['int', 'long', 'float', 'double', 'decimal'])

            if not is_numeric:
                report.add_error(
                    'type',
                    f"Column '{col}' should be numeric but is {dtype}",
                    column=col,
                    actual_type=dtype
                )

    def _validate_ranges(self, report: ValidationReport):
        """Validate values are within expected ranges."""
        ranges = self.get_valid_ranges()

        for col, (min_val, max_val) in ranges.items():
            if col not in self.columns:
                continue

            if self.backend == 'spark':
                from pyspark.sql import functions as F
                stats = self.df.agg(
                    F.min(col).alias('min'),
                    F.max(col).alias('max')
                ).collect()[0]
                actual_min, actual_max = stats['min'], stats['max']
            else:
                actual_min = self.df[col].min()
                actual_max = self.df[col].max()

            if min_val is not None and actual_min is not None and actual_min < min_val:
                report.add_warning(
                    'range',
                    f"Column '{col}' has values below minimum: {actual_min} < {min_val}",
                    column=col,
                    actual_min=actual_min,
                    expected_min=min_val
                )

            if max_val is not None and actual_max is not None and actual_max > max_val:
                report.add_warning(
                    'range',
                    f"Column '{col}' has values above maximum: {actual_max} > {max_val}",
                    column=col,
                    actual_max=actual_max,
                    expected_max=max_val
                )

    def _validate_nulls(self, report: ValidationReport):
        """Validate null percentages are within thresholds."""
        thresholds = self.get_null_thresholds()
        total_rows = self.row_count

        if total_rows == 0:
            return

        # Check required columns for nulls (default: 0% allowed)
        required_cols = set(self.get_required_columns())

        for col in required_cols:
            if col not in self.columns:
                continue

            threshold = thresholds.get(col, 0.0)

            if self.backend == 'spark':
                from pyspark.sql import functions as F
                null_count = self.df.filter(F.col(col).isNull()).count()
            else:
                null_count = self.df[col].isna().sum()

            null_pct = null_count / total_rows

            if null_pct > threshold:
                level = 'error' if threshold == 0.0 else 'warning'
                if level == 'error':
                    report.add_error(
                        'quality',
                        f"Column '{col}' has {null_pct:.1%} nulls (max {threshold:.1%})",
                        column=col,
                        null_count=null_count,
                        null_pct=null_pct,
                        threshold=threshold
                    )
                else:
                    report.add_warning(
                        'quality',
                        f"Column '{col}' has {null_pct:.1%} nulls (max {threshold:.1%})",
                        column=col,
                        null_count=null_count,
                        null_pct=null_pct,
                        threshold=threshold
                    )

    def _validate_time_series(self, report: ValidationReport):
        """Validate time series properties (gaps, coverage)."""
        date_col = self.get_date_column()
        if not date_col or date_col not in self.columns:
            return

        entity_col = self.get_entity_column()

        if self.backend == 'spark':
            from pyspark.sql import functions as F

            # Get date range
            stats = self.df.agg(
                F.min(date_col).alias('min_date'),
                F.max(date_col).alias('max_date'),
                F.countDistinct(date_col).alias('unique_dates')
            ).collect()[0]

            min_date = stats['min_date']
            max_date = stats['max_date']
            unique_dates = stats['unique_dates']

            # Count entities if applicable
            if entity_col and entity_col in self.columns:
                entity_count = self.df.select(entity_col).distinct().count()
                report.metrics['entity_count'] = entity_count

        else:
            min_date = self.df[date_col].min()
            max_date = self.df[date_col].max()
            unique_dates = self.df[date_col].nunique()

            if entity_col and entity_col in self.columns:
                entity_count = self.df[entity_col].nunique()
                report.metrics['entity_count'] = entity_count

        report.metrics['date_range'] = f"{min_date} to {max_date}"
        report.metrics['unique_dates'] = unique_dates

        # Check for reasonable date coverage
        if unique_dates < 5:
            report.add_warning(
                'coverage',
                f"Only {unique_dates} unique dates - may be insufficient for time series",
                unique_dates=unique_dates
            )

    def _collect_metrics(self, report: ValidationReport):
        """Collect general metrics about the data."""
        report.metrics['row_count'] = self.row_count
        report.metrics['column_count'] = len(self.columns)

        # Numeric column stats
        numeric_cols = [c for c in self.get_numeric_columns() if c in self.columns]
        if numeric_cols and self.row_count > 0:
            if self.backend == 'spark':
                # Get summary stats for key column (first numeric)
                col = numeric_cols[0]
                from pyspark.sql import functions as F
                stats = self.df.agg(
                    F.mean(col).alias('mean'),
                    F.stddev(col).alias('std'),
                    F.min(col).alias('min'),
                    F.max(col).alias('max')
                ).collect()[0]
                report.metrics[f'{col}_mean'] = stats['mean']
                report.metrics[f'{col}_std'] = stats['std']
            else:
                col = numeric_cols[0]
                report.metrics[f'{col}_mean'] = float(self.df[col].mean())
                report.metrics[f'{col}_std'] = float(self.df[col].std())
