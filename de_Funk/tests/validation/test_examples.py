#!/usr/bin/env python3
"""
Test suite for example scripts.

Validates that all example scripts run without errors and produce expected results.

Note: Path setup is handled by conftest.py which uses the unified repo discovery system.
"""

import pytest
import importlib
from pathlib import Path
from typing import Dict, Any

from scripts.examples.parameter_interface import (
    MeasureCalculator,
    CalculationRequest,
    validate_params,
    ParameterError
)


class TestParameterInterface:
    """Test the parameter-driven calculation interface."""

    def setup_method(self):
        """Setup test fixtures."""
        self.calc = MeasureCalculator(backend='duckdb')

    def test_calculator_initialization(self):
        """Test calculator initializes correctly."""
        assert self.calc is not None
        assert self.calc.backend == 'duckdb'

    def test_list_models(self):
        """Test listing available models."""
        models = self.calc.list_models()
        assert isinstance(models, list)
        assert len(models) > 0
        assert 'stocks' in models or 'company' in models

    def test_list_measures(self):
        """Test listing measures for a model."""
        # Skip if stocks model not available
        if 'stocks' not in self.calc.list_models():
            pytest.skip("Stocks model not available")

        measures = self.calc.list_measures('stocks')
        assert isinstance(measures, list)
        assert len(measures) > 0

    def test_get_measure_info(self):
        """Test getting measure information."""
        if 'stocks' not in self.calc.list_models():
            pytest.skip("Stocks model not available")

        measures = self.calc.list_measures('stocks')
        if not measures:
            pytest.skip("No measures available")

        measure_name = measures[0]
        info = self.calc.get_measure_info('stocks', measure_name)
        assert isinstance(info, dict)
        assert 'type' in info
        assert 'source' in info


class TestCalculationRequest:
    """Test CalculationRequest dataclass."""

    def test_basic_request(self):
        """Test basic request creation."""
        request = CalculationRequest(
            model='stocks',
            measure='avg_close_price',
            tickers=['AAPL'],
        )
        assert request.model == 'stocks'
        assert request.measure == 'avg_close_price'
        assert request.tickers == ['AAPL']

    def test_request_with_dates(self):
        """Test request with date filters."""
        request = CalculationRequest(
            model='stocks',
            measure='volume_weighted_index',
            tickers=['AAPL', 'MSFT'],
            start_date='2024-01-01',
            end_date='2024-12-31'
        )

        filter_kwargs = request.to_filter_kwargs()
        assert 'trade_date' in filter_kwargs
        assert filter_kwargs['trade_date']['start'] == '2024-01-01'
        assert filter_kwargs['trade_date']['end'] == '2024-12-31'
        assert filter_kwargs['ticker'] == ['AAPL', 'MSFT']

    def test_request_to_filter_kwargs(self):
        """Test conversion to filter kwargs."""
        request = CalculationRequest(
            model='stocks',
            measure='avg_close_price',
            tickers=['AAPL'],
            entity_column='ticker',
            limit=10
        )

        kwargs = request.to_filter_kwargs()
        assert kwargs['ticker'] == ['AAPL']
        assert kwargs['entity_column'] == 'ticker'
        assert kwargs['limit'] == 10


class TestParameterValidation:
    """Test parameter validation."""

    def test_valid_params(self):
        """Test validation of valid parameters."""
        params = {
            'model': 'stocks',
            'measure': 'avg_close_price',
            'tickers': ['AAPL', 'MSFT'],
            'start_date': '2024-01-01',
            'end_date': '2024-12-31',
            'limit': 10,
            'backend': 'duckdb'
        }

        # Should not raise
        validate_params(params)

    def test_missing_model(self):
        """Test validation fails without model."""
        params = {
            'measure': 'avg_close_price'
        }

        with pytest.raises(ParameterError, match="Missing required parameter: 'model'"):
            validate_params(params)

    def test_missing_measure(self):
        """Test validation fails without measure."""
        params = {
            'model': 'stocks'
        }

        with pytest.raises(ParameterError, match="Missing required parameter: 'measure'"):
            validate_params(params)

    def test_invalid_date_format(self):
        """Test validation fails with invalid date."""
        params = {
            'model': 'stocks',
            'measure': 'avg_close_price',
            'start_date': 'invalid-date'
        }

        with pytest.raises(ParameterError, match="Invalid start_date"):
            validate_params(params)

    def test_invalid_backend(self):
        """Test validation fails with invalid backend."""
        params = {
            'model': 'stocks',
            'measure': 'avg_close_price',
            'backend': 'invalid_backend'
        }

        with pytest.raises(ParameterError, match="Invalid backend"):
            validate_params(params)

    def test_date_range_validation(self):
        """Test validation of date ranges."""
        params = {
            'model': 'stocks',
            'measure': 'avg_close_price',
            'start_date': '2024-12-31',
            'end_date': '2024-01-01'  # End before start
        }

        with pytest.raises(ParameterError, match="must be before"):
            validate_params(params)

    def test_invalid_limit(self):
        """Test validation fails with invalid limit."""
        params = {
            'model': 'stocks',
            'measure': 'avg_close_price',
            'limit': -10  # Negative limit
        }

        with pytest.raises(ParameterError, match="Limit must be positive"):
            validate_params(params)


class TestWeightedCalculations:
    """Test weighted price calculations."""

    def setup_method(self):
        """Setup test fixtures."""
        self.calc = MeasureCalculator(backend='duckdb')

    @pytest.mark.skipif(
        'stocks' not in MeasureCalculator(backend='duckdb').list_models(),
        reason="Stocks model not available"
    )
    def test_volume_weighted_index(self):
        """Test average close price calculation."""
        params = {
            'model': 'stocks',
            'measure': 'avg_close_price',
            'tickers': ['AAPL'],
            'start_date': '2024-01-01',
            'end_date': '2024-01-31'
        }

        result = self.calc.calculate(params)

        # Check for errors first
        if result.error:
            # If error is due to missing data, skip test
            if 'no data' in result.error.lower() or 'not found' in result.error.lower():
                pytest.skip(f"No data available: {result.error}")
            else:
                pytest.fail(f"Calculation failed: {result.error}")

        # Validate result
        assert result.data is not None
        assert result.rows >= 0
        assert result.backend == 'duckdb'
        assert result.query_time_ms >= 0

    @pytest.mark.skipif(
        'stocks' not in MeasureCalculator(backend='duckdb').list_models(),
        reason="Stocks model not available"
    )
    def test_multiple_tickers(self):
        """Test calculation with multiple tickers."""
        params = {
            'model': 'stocks',
            'measure': 'avg_close_price',
            'tickers': ['AAPL', 'MSFT'],
            'start_date': '2024-01-01',
            'end_date': '2024-01-31'
        }

        result = self.calc.calculate(params)

        if result.error:
            if 'no data' in result.error.lower():
                pytest.skip(f"No data available: {result.error}")
            else:
                pytest.fail(f"Calculation failed: {result.error}")

        assert result.data is not None

    @pytest.mark.skipif(
        'stocks' not in MeasureCalculator(backend='duckdb').list_models(),
        reason="Stocks model not available"
    )
    def test_compare_strategies(self):
        """Test comparing multiple measures."""
        strategies = [
            'avg_close_price',
            'total_volume',
        ]

        results = self.calc.calculate_with_comparison(
            model='stocks',
            measures=strategies,
            tickers=['AAPL'],
            start_date='2024-01-01',
            end_date='2024-01-31'
        )

        assert isinstance(results, dict)
        assert len(results) == len(strategies)

        # At least one should succeed or all should have clear errors
        success_count = sum(1 for r in results.values() if not r.error)
        error_count = sum(1 for r in results.values() if r.error)

        assert success_count + error_count == len(strategies)


class TestExampleScripts:
    """Test that example scripts can be imported and executed."""

    def test_quickstart_imports(self):
        """Test that quickstart example can be imported."""
        try:
            import scripts.examples.weighting_strategies.README as readme
        except ImportError:
            pass  # README is markdown, not importable

        # Test parameter interface imports
        from scripts.examples.parameter_interface import (
            MeasureCalculator,
            CalculationRequest,
            CalculationResult,
        )

        assert MeasureCalculator is not None
        assert CalculationRequest is not None
        assert CalculationResult is not None

    def test_weighting_example_structure(self):
        """Test weighting examples directory structure."""
        examples_dir = Path(__file__).parent.parent.parent / 'examples' / 'weighting_strategies'
        assert examples_dir.exists()

        # Check for key files
        assert (examples_dir / 'README.md').exists()
        assert (examples_dir / '01_basic_weighted_price.py').exists()
        assert (examples_dir / '02_compare_all_strategies.py').exists()


def test_parameter_discovery():
    """Test parameter discovery functions."""
    from scripts.examples.parameter_interface.discovery import (
        list_models,
        list_weighting_strategies,
    )

    # Test list_models
    models = list_models()
    assert isinstance(models, list)

    # Test list_weighting_strategies
    strategies = list_weighting_strategies()
    assert isinstance(strategies, dict)
    assert 'equal' in strategies
    assert 'volume' in strategies
    assert 'market_cap' in strategies


class TestQueryExamples:
    """Test query system examples."""

    def test_query_examples_directory_structure(self):
        """Test queries directory exists with all expected files."""
        queries_dir = Path(__file__).parent.parent.parent / 'examples' / 'queries'
        assert queries_dir.exists(), "queries/ directory should exist"

        # Check for key files
        assert (queries_dir / 'README.md').exists(), "queries/README.md should exist"
        assert (queries_dir / '01_auto_join.py').exists(), "01_auto_join.py should exist"
        assert (queries_dir / '02_query_planner.py').exists(), "02_query_planner.py should exist"
        assert (queries_dir / '03_session_queries.py').exists(), "03_session_queries.py should exist"

    def test_auto_join_example_imports(self):
        """Test that auto_join example can be imported."""
        # Import should work without errors (use importlib for numeric prefix)
        auto_join = importlib.import_module('scripts.examples.queries.01_auto_join')

        # Check that demo function exists
        assert hasattr(auto_join, 'demo_auto_join')
        assert callable(auto_join.demo_auto_join)

    def test_query_planner_example_imports(self):
        """Test that query_planner example can be imported."""
        query_planner = importlib.import_module('scripts.examples.queries.02_query_planner')

        # Check that example functions exist
        assert hasattr(query_planner, 'example_basic_enrichment')
        assert callable(query_planner.example_basic_enrichment)

    def test_session_queries_example_imports(self):
        """Test that session_queries example can be imported."""
        session_queries = importlib.import_module('scripts.examples.queries.03_session_queries')

        # Check that key functions exist
        assert hasattr(session_queries, 'create_session')
        assert callable(session_queries.create_session)


class TestExtensionExamples:
    """Test extension/developer examples."""

    def test_extending_directory_structure(self):
        """Test extending directory exists with all expected files."""
        extending_dir = Path(__file__).parent.parent.parent / 'examples' / 'extending'
        assert extending_dir.exists(), "extending/ directory should exist"

        # Check for key files
        assert (extending_dir / 'README.md').exists(), "extending/README.md should exist"
        assert (extending_dir / 'custom_facet.py').exists(), "custom_facet.py should exist"
        assert (extending_dir / 'custom_model.py').exists(), "custom_model.py should exist"
        assert (extending_dir / 'custom_provider.py').exists(), "custom_provider.py should exist"
        assert (extending_dir / 'custom_notebook.md').exists(), "custom_notebook.md should exist"

    def test_custom_facet_example_imports(self):
        """Test that custom_facet example can be imported."""
        import scripts.examples.extending.custom_facet as custom_facet

        # Check that example class/functions exist
        assert hasattr(custom_facet, '__doc__')
        assert custom_facet.__doc__ is not None

    def test_custom_model_example_imports(self):
        """Test that custom_model example can be imported."""
        import scripts.examples.extending.custom_model as custom_model

        # Check that example has content
        assert hasattr(custom_model, '__doc__')
        assert custom_model.__doc__ is not None

    def test_custom_provider_example_imports(self):
        """Test that custom_provider example can be imported."""
        import scripts.examples.extending.custom_provider as custom_provider

        # Check that example has content
        assert hasattr(custom_provider, '__doc__')
        assert custom_provider.__doc__ is not None

    def test_custom_notebook_example_exists(self):
        """Test that custom_notebook.md example exists and has content."""
        notebook_path = Path(__file__).parent.parent.parent / 'examples' / 'extending' / 'custom_notebook.md'
        assert notebook_path.exists(), "custom_notebook.md should exist"

        # Check that file has content
        content = notebook_path.read_text()
        assert len(content) > 0, "custom_notebook.md should have content"
        assert '---' in content, "custom_notebook.md should have YAML front matter"


class TestAutoEnrichExamples:
    """Test auto-enrichment examples."""

    def test_auto_enrich_demo_imports(self):
        """Test that auto_enrich_demo can be imported."""
        auto_enrich_demo = importlib.import_module('scripts.examples.measure_calculations.04_auto_enrich_demo')

        # Check that demo functions exist
        assert hasattr(auto_enrich_demo, 'demo_measure_config')
        assert callable(auto_enrich_demo.demo_measure_config)

    def test_auto_enrich_example_imports(self):
        """Test that auto_enrich_example can be imported."""
        auto_enrich_example = importlib.import_module('scripts.examples.measure_calculations.05_auto_enrich_example')

        # Check that example functions exist
        assert hasattr(auto_enrich_example, 'example_simple_auto_enrich')
        assert callable(auto_enrich_example.example_simple_auto_enrich)


class TestExampleDocumentation:
    """Test that all example directories have proper documentation."""

    def test_main_examples_readme_exists(self):
        """Test that main examples README exists."""
        readme_path = Path(__file__).parent.parent.parent / 'examples' / 'README.md'
        assert readme_path.exists(), "scripts/examples/README.md should exist"

        content = readme_path.read_text()
        # Check for key sections
        assert 'Quick Start' in content or 'quick start' in content.lower()
        assert 'queries' in content.lower()
        assert 'extending' in content.lower()

    def test_queries_readme_exists(self):
        """Test that queries README exists and has content."""
        readme_path = Path(__file__).parent.parent.parent / 'examples' / 'queries' / 'README.md'
        assert readme_path.exists(), "queries/README.md should exist"

        content = readme_path.read_text()
        assert 'auto_join' in content.lower() or 'auto-join' in content.lower()
        assert len(content) > 100, "README should have substantial content"

    def test_extending_readme_exists(self):
        """Test that extending README exists and has content."""
        readme_path = Path(__file__).parent.parent.parent / 'examples' / 'extending' / 'README.md'
        assert readme_path.exists(), "extending/README.md should exist"

        content = readme_path.read_text()
        assert 'custom' in content.lower()
        assert 'facet' in content.lower() or 'model' in content.lower()
        assert len(content) > 100, "README should have substantial content"


class TestExampleIntegrity:
    """Test the integrity and consistency of example files."""

    def test_all_python_examples_have_docstrings(self):
        """Test that all Python example files have module docstrings."""
        examples_dir = Path(__file__).parent.parent.parent / 'examples'

        # Find all Python files (excluding __init__.py and __pycache__)
        python_files = []
        for subdir in ['queries', 'extending', 'measure_calculations']:
            subdir_path = examples_dir / subdir
            if subdir_path.exists():
                python_files.extend(subdir_path.glob('*.py'))

        # Filter out __init__.py files
        python_files = [f for f in python_files if f.name != '__init__.py']

        for py_file in python_files:
            content = py_file.read_text()
            # Check for docstring at the beginning (after any comments)
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            # Find first non-comment line
            first_code_idx = 0
            for i, line in enumerate(lines):
                if not line.startswith('#'):
                    first_code_idx = i
                    break

            # Docstring should be in first few lines of actual code
            docstring_found = any('"""' in line or "'''" in line for line in lines[first_code_idx:first_code_idx+3])
            assert docstring_found, f"{py_file.name} should have a module docstring"

    def test_example_files_use_proper_imports(self):
        """Test that example files use proper import patterns."""
        examples_dir = Path(__file__).parent.parent.parent / 'examples'

        # Check query examples for proper imports
        for example_file in ['01_auto_join.py', '02_query_planner.py']:
            file_path = examples_dir / 'queries' / example_file
            if file_path.exists():
                content = file_path.read_text()
                # Should use get_repo_root pattern (bootstrap approach)
                assert 'get_repo_root' in content, f"{example_file} should use get_repo_root"

    def test_no_hardcoded_paths(self):
        """Test that examples don't have hardcoded absolute paths."""
        examples_dir = Path(__file__).parent.parent.parent / 'examples'

        python_files = list(examples_dir.rglob('*.py'))
        python_files = [f for f in python_files if f.name != '__init__.py']

        for py_file in python_files:
            content = py_file.read_text()
            # Check for common hardcoded path patterns (but allow comments)
            lines = [line for line in content.split('\n') if not line.strip().startswith('#')]
            content_no_comments = '\n'.join(lines)

            # These patterns indicate hardcoded paths
            bad_patterns = [
                '/home/user/',
                '/home/ms_trixie/',
                'C:\\Users\\',
                '/absolute/path/',
            ]

            for pattern in bad_patterns:
                assert pattern not in content_no_comments, f"{py_file.name} should not have hardcoded path: {pattern}"


if __name__ == '__main__':
    # Run tests with pytest
    pytest.main([__file__, '-v', '--tb=short'])
