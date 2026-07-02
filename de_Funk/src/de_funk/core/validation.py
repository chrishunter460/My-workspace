"""
Validation layer for notebooks.

Validates notebook configurations against available models.
"""

from typing import List, Tuple, Optional
from dataclasses import dataclass

# ModelRegistry removed — use DomainConfigLoader via DeFunk.from_config()
ModelRegistry = None

# NotebookConfig/Exhibit were from the old Streamlit notebook path (removed).
# Validation still works — it just validates model configs, not notebook schemas.
NotebookConfig = None
Exhibit = None


@dataclass
class ValidationError:
    """Represents a validation error."""
    level: str  # 'error' or 'warning'
    message: str
    location: Optional[str] = None  # e.g., 'exhibits[0]', 'variables.time'


class NotebookValidator:
    """
    Validates notebook configuration against available models.

    Checks:
    - Referenced models exist
    - Tables/sources exist in models
    - Measures exist in models
    - Columns exist in tables
    - Filter references are valid
    """

    def __init__(self, model_registry: ModelRegistry):
        """
        Initialize validator.

        Args:
            model_registry: Model registry for validation
        """
        self.model_registry = model_registry

    def validate(self, notebook_config: NotebookConfig) -> List[ValidationError]:
        """
        Validate notebook configuration.

        Args:
            notebook_config: Notebook configuration to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Validate models exist
        errors.extend(self._validate_models(notebook_config))

        # Validate exhibits
        for i, exhibit in enumerate(notebook_config.exhibits):
            errors.extend(self._validate_exhibit(exhibit, i))

        return errors

    def _validate_models(self, notebook_config: NotebookConfig) -> List[ValidationError]:
        """Validate referenced models exist."""
        errors = []

        # Get models from exhibits
        models_used = set()
        for exhibit in notebook_config.exhibits:
            if hasattr(exhibit, 'source') and exhibit.source:
                model_name = self._parse_source(exhibit.source)[0]
                models_used.add(model_name)

        # Check each model exists
        available_models = self.model_registry.list_models()
        for model_name in models_used:
            if model_name not in available_models:
                errors.append(ValidationError(
                    level='error',
                    message=f"Model '{model_name}' not found. Available models: {available_models}",
                    location='models'
                ))

        return errors

    def _validate_exhibit(self, exhibit: Exhibit, index: int) -> List[ValidationError]:
        """Validate a single exhibit."""
        errors = []
        location = f"exhibits[{index}] ({exhibit.id})"

        # Validate source
        if not hasattr(exhibit, 'source') or not exhibit.source:
            errors.append(ValidationError(
                level='error',
                message=f"Exhibit '{exhibit.id}' missing source",
                location=location
            ))
            return errors

        # Parse source
        try:
            model_name, table_name = self._parse_source(exhibit.source)
        except ValueError as e:
            errors.append(ValidationError(
                level='error',
                message=str(e),
                location=f"{location}.source"
            ))
            return errors

        # Check model exists
        if not self.model_registry.has_model(model_name):
            errors.append(ValidationError(
                level='error',
                message=f"Model '{model_name}' not found",
                location=f"{location}.source"
            ))
            return errors

        model = self.model_registry.get_model(model_name)

        # Check table exists
        if not model.has_table(table_name):
            available_tables = model.list_tables()
            errors.append(ValidationError(
                level='error',
                message=f"Table '{table_name}' not found in model '{model_name}'. Available: {available_tables}",
                location=f"{location}.source"
            ))
            return errors

        # Get table schema
        table_schema = model.get_table_columns(table_name)

        # Validate measures if present
        if hasattr(exhibit, 'measures') and exhibit.measures:
            for measure_id in exhibit.measures:
                if not model.has_measure(measure_id):
                    available_measures = model.list_measures()
                    errors.append(ValidationError(
                        level='error',
                        message=f"Measure '{measure_id}' not found in model '{model_name}'. Available: {available_measures}",
                        location=f"{location}.measures"
                    ))

        # Validate x_axis dimension
        if hasattr(exhibit, 'x_axis') and exhibit.x_axis:
            if isinstance(exhibit.x_axis, str):
                x_col = exhibit.x_axis
            elif hasattr(exhibit.x_axis, 'dimension'):
                x_col = exhibit.x_axis.dimension
            else:
                x_col = None

            if x_col and x_col not in table_schema:
                errors.append(ValidationError(
                    level='error',
                    message=f"Column '{x_col}' not found in table '{table_name}'. Available: {list(table_schema.keys())}",
                    location=f"{location}.x_axis"
                ))

        # Validate columns for data tables
        if hasattr(exhibit, 'columns') and exhibit.columns:
            for col in exhibit.columns:
                if col not in table_schema:
                    errors.append(ValidationError(
                        level='warning',
                        message=f"Column '{col}' not found in table '{table_name}'. Available: {list(table_schema.keys())}",
                        location=f"{location}.columns"
                    ))

        # Validate filters reference valid columns
        if hasattr(exhibit, 'filters') and exhibit.filters:
            errors.extend(self._validate_filters(exhibit.filters, table_schema, location))

        return errors

    def _validate_filters(
        self,
        filters: dict,
        table_schema: dict,
        location: str
    ) -> List[ValidationError]:
        """Validate filter references."""
        errors = []

        for filter_col, filter_value in filters.items():
            # Skip variable references (start with $)
            if isinstance(filter_value, str) and filter_value.startswith('$'):
                continue

            # Check column exists
            if filter_col not in table_schema:
                errors.append(ValidationError(
                    level='warning',
                    message=f"Filter column '{filter_col}' not found in table. Available: {list(table_schema.keys())}",
                    location=f"{location}.filters"
                ))

        return errors

    def _parse_source(self, source: str) -> Tuple[str, str]:
        """
        Parse source string into (model_name, table_name).

        Args:
            source: Source string (e.g., "company.fact_prices")

        Returns:
            Tuple of (model_name, table_name)

        Raises:
            ValueError: If source format is invalid
        """
        parts = source.split('.')
        if len(parts) != 2:
            raise ValueError(f"Invalid source format: '{source}'. Expected 'model.table'")
        return parts[0], parts[1]

    def validate_and_raise(self, notebook_config: NotebookConfig):
        """
        Validate and raise exception if errors found.

        Args:
            notebook_config: Notebook configuration

        Raises:
            ValueError: If validation errors found
        """
        errors = self.validate(notebook_config)

        # Filter to just errors (not warnings)
        error_list = [e for e in errors if e.level == 'error']

        if error_list:
            error_messages = '\n'.join([
                f"  [{e.level.upper()}] {e.location}: {e.message}"
                for e in error_list
            ])
            raise ValueError(f"Notebook validation failed:\n{error_messages}")

    def get_warnings(self, notebook_config: NotebookConfig) -> List[ValidationError]:
        """Get only validation warnings."""
        errors = self.validate(notebook_config)
        return [e for e in errors if e.level == 'warning']

    def get_errors(self, notebook_config: NotebookConfig) -> List[ValidationError]:
        """Get only validation errors."""
        errors = self.validate(notebook_config)
        return [e for e in errors if e.level == 'error']

    def is_valid(self, notebook_config: NotebookConfig) -> bool:
        """
        Check if notebook is valid (no errors).

        Args:
            notebook_config: Notebook configuration

        Returns:
            True if valid (no errors), False otherwise
        """
        errors = self.get_errors(notebook_config)
        return len(errors) == 0
