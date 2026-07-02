"""
Core calculator module for parameter-driven measure calculations.

This module provides the MeasureCalculator class which accepts parameter dictionaries
and returns calculation results.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
import sys
from pathlib import Path

# Bootstrap: add repo to path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from de_funk.utils.repo import get_repo_root
repo_root = get_repo_root()

# Now import project dependencies
import pandas as pd
from de_funk.core.context import RepoContext
from de_funk.models.api.session import UniversalSession


@dataclass
class CalculationRequest:
    """
    A calculation request with parameters.

    Attributes:
        model: Model name (e.g., 'equity', 'corporate', 'macro')
        measure: Measure name (e.g., 'avg_close_price', 'volume_weighted_index')
        tickers: Optional list of ticker symbols to filter by
        start_date: Optional start date for filtering (YYYY-MM-DD)
        end_date: Optional end date for filtering (YYYY-MM-DD)
        entity_column: Optional entity column for grouping (e.g., 'ticker')
        limit: Optional limit on number of results
        additional_filters: Optional dictionary of additional filter parameters
        backend: Backend to use ('duckdb' or 'spark'), defaults to 'duckdb'

    Example:
        request = CalculationRequest(
            model='equity',
            measure='volume_weighted_index',
            tickers=['AAPL', 'MSFT', 'GOOGL'],
            start_date='2024-01-01',
            end_date='2024-12-31'
        )
    """
    model: str
    measure: str
    tickers: Optional[List[str]] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    entity_column: Optional[str] = None
    limit: Optional[int] = None
    additional_filters: Dict[str, Any] = field(default_factory=dict)
    backend: str = 'duckdb'

    def to_filter_kwargs(self) -> Dict[str, Any]:
        """Convert request to filter kwargs for model.calculate_measure()."""
        filter_kwargs = {}

        # Add date range filter
        if self.start_date or self.end_date:
            date_filter = {}
            if self.start_date:
                date_filter['start'] = self.start_date
            if self.end_date:
                date_filter['end'] = self.end_date
            filter_kwargs['trade_date'] = date_filter

        # Add ticker filter
        if self.tickers:
            filter_kwargs['ticker'] = self.tickers

        # Add entity column
        if self.entity_column:
            filter_kwargs['entity_column'] = self.entity_column

        # Add limit
        if self.limit:
            filter_kwargs['limit'] = self.limit

        # Add additional filters
        filter_kwargs.update(self.additional_filters)

        return filter_kwargs


@dataclass
class CalculationResult:
    """
    Result of a calculation request.

    Attributes:
        data: The resulting DataFrame
        request: The original request
        backend: Backend used for calculation
        query_time_ms: Query execution time in milliseconds
        rows: Number of rows returned
        columns: List of column names
        error: Error message if calculation failed
        metadata: Additional metadata about the calculation
    """
    data: Optional[pd.DataFrame] = None
    request: Optional[CalculationRequest] = None
    backend: str = 'duckdb'
    query_time_ms: float = 0.0
    rows: int = 0
    columns: List[str] = field(default_factory=list)
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Extract metadata from data if available."""
        if self.data is not None and not self.data.empty:
            self.rows = len(self.data)
            self.columns = list(self.data.columns)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary (without DataFrame for serialization)."""
        return {
            'backend': self.backend,
            'query_time_ms': self.query_time_ms,
            'rows': self.rows,
            'columns': self.columns,
            'error': self.error,
            'metadata': self.metadata,
        }

    def summary(self) -> str:
        """Generate a human-readable summary of the result."""
        if self.error:
            return f"Error: {self.error}"

        summary_lines = [
            f"Backend: {self.backend}",
            f"Query Time: {self.query_time_ms:.2f}ms",
            f"Rows: {self.rows}",
            f"Columns: {', '.join(self.columns)}",
        ]

        if self.metadata:
            summary_lines.append(f"Metadata: {self.metadata}")

        return "\n".join(summary_lines)


class MeasureCalculator:
    """
    Main calculator class for parameter-driven measure calculations.

    This class provides a simple interface for running measure calculations
    using parameter dictionaries.

    Example:
        # Initialize calculator
        calc = MeasureCalculator(backend='duckdb')

        # Run a calculation
        result = calc.calculate({
            'model': 'equity',
            'measure': 'volume_weighted_index',
            'tickers': ['AAPL', 'MSFT', 'GOOGL'],
            'start_date': '2024-01-01',
            'end_date': '2024-12-31'
        })

        # Access results
        print(result.data)
        print(result.summary())
    """

    def __init__(self, backend: str = 'duckdb', repo_root: Optional[Path] = None):
        """
        Initialize the calculator.

        Args:
            backend: Backend to use ('duckdb' or 'spark')
            repo_root: Optional repo root path (auto-detected if not provided)
        """
        self.backend = backend
        self.repo_root = repo_root
        self._ctx = None
        self._session = None
        self._models = {}

    @property
    def ctx(self) -> RepoContext:
        """Lazy-load repo context."""
        if self._ctx is None:
            self._ctx = RepoContext.from_repo_root(connection_type=self.backend)
        return self._ctx

    @property
    def session(self) -> UniversalSession:
        """Lazy-load universal session."""
        if self._session is None:
            self._session = UniversalSession(
                connection=self.ctx.connection,
                storage_cfg=self.ctx.storage,
                repo_root=self.ctx.repo
            )
        return self._session

    def get_model(self, model_name: str):
        """
        Get a model instance by name.

        Args:
            model_name: Name of the model (e.g., 'equity', 'corporate')

        Returns:
            Model instance
        """
        if model_name not in self._models:
            self._models[model_name] = self.session.get_model_instance(model_name)
        return self._models[model_name]

    def calculate(self, params: Union[Dict[str, Any], CalculationRequest]) -> CalculationResult:
        """
        Run a calculation with the given parameters.

        Args:
            params: Either a dict or CalculationRequest object with calculation parameters

        Returns:
            CalculationResult with data and metadata

        Example:
            result = calc.calculate({
                'model': 'equity',
                'measure': 'avg_close_price',
                'tickers': ['AAPL', 'MSFT'],
                'entity_column': 'ticker',
                'limit': 10
            })
        """
        # Convert dict to CalculationRequest if needed
        if isinstance(params, dict):
            request = CalculationRequest(**params)
        else:
            request = params

        try:
            # Get model
            model = self.get_model(request.model)

            # Convert request to filter kwargs
            filter_kwargs = request.to_filter_kwargs()

            # Execute calculation
            measure_result = model.calculate_measure(
                measure_name=request.measure,
                **filter_kwargs
            )

            # Create result object
            result = CalculationResult(
                data=measure_result.data,
                request=request,
                backend=measure_result.backend,
                query_time_ms=measure_result.query_time_ms,
                rows=measure_result.rows,
                metadata={
                    'model': request.model,
                    'measure': request.measure,
                }
            )

            return result

        except Exception as e:
            # Return error result
            return CalculationResult(
                request=request,
                error=str(e),
                backend=self.backend,
            )

    def calculate_multiple(self, requests: List[Union[Dict[str, Any], CalculationRequest]]) -> List[CalculationResult]:
        """
        Run multiple calculations in sequence.

        Args:
            requests: List of calculation requests (dicts or CalculationRequest objects)

        Returns:
            List of CalculationResult objects

        Example:
            results = calc.calculate_multiple([
                {'model': 'equity', 'measure': 'avg_close_price', 'tickers': ['AAPL']},
                {'model': 'equity', 'measure': 'total_volume', 'tickers': ['AAPL']},
            ])
        """
        return [self.calculate(req) for req in requests]

    def calculate_with_comparison(
        self,
        model: str,
        measures: List[str],
        tickers: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs
    ) -> Dict[str, CalculationResult]:
        """
        Calculate multiple measures for comparison.

        Args:
            model: Model name
            measures: List of measure names
            tickers: Optional ticker filter
            start_date: Optional start date
            end_date: Optional end date
            **kwargs: Additional filter parameters

        Returns:
            Dictionary mapping measure name to CalculationResult

        Example:
            results = calc.calculate_with_comparison(
                model='equity',
                measures=['equal_weighted_index', 'volume_weighted_index', 'market_cap_weighted_index'],
                tickers=['AAPL', 'MSFT', 'GOOGL'],
                start_date='2024-01-01',
                end_date='2024-12-31'
            )
        """
        results = {}

        for measure in measures:
            request = CalculationRequest(
                model=model,
                measure=measure,
                tickers=tickers,
                start_date=start_date,
                end_date=end_date,
                additional_filters=kwargs
            )
            results[measure] = self.calculate(request)

        return results

    def list_models(self) -> List[str]:
        """
        List available models.

        Returns:
            List of model names
        """
        return list(self.session.registry.models.keys())

    def list_measures(self, model_name: str) -> List[str]:
        """
        List available measures for a model.

        Args:
            model_name: Name of the model

        Returns:
            List of measure names
        """
        model = self.get_model(model_name)
        return list(model.measures.list_measures().keys())

    def get_measure_info(self, model_name: str, measure_name: str) -> Dict[str, Any]:
        """
        Get information about a specific measure.

        Args:
            model_name: Name of the model
            measure_name: Name of the measure

        Returns:
            Dictionary with measure information
        """
        model = self.get_model(model_name)
        return model.measures.get_measure_info(measure_name)
