"""
Parameter and measure discovery module.

Provides functions to discover available models, measures, and their parameters.
"""

from typing import Any, Dict, List, Optional
import sys
from pathlib import Path

# Bootstrap: add repo to path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from de_funk.utils.repo import get_repo_root
repo_root = get_repo_root()

from de_funk.core.context import RepoContext
from de_funk.models.api.session import UniversalSession


def discover_measures(model_name: Optional[str] = None, backend: str = 'duckdb') -> Dict[str, Any]:
    """
    Discover available measures.

    Args:
        model_name: Optional model name to filter by
        backend: Backend to use (default: 'duckdb')

    Returns:
        Dictionary with model -> measures mapping and details

    Example:
        # Discover all measures
        all_measures = discover_measures()
        print(f"Models: {list(all_measures.keys())}")

        # Discover measures for specific model
        equity_measures = discover_measures('equity')
        print(f"Equity measures: {equity_measures['equity']['measures']}")
    """
    ctx = RepoContext.from_repo_root(connection_type=backend)
    session = UniversalSession(
        connection=ctx.connection,
        storage_cfg=ctx.storage,
        repo_root=ctx.repo
    )

    result = {}

    # Get models to query
    if model_name:
        model_names = [model_name]
    else:
        model_names = list(session.registry.models.keys())

    # Query each model
    for name in model_names:
        try:
            model = session.get_model_instance(name)
            measures = model.measures.list_measures()

            # Get detailed info for each measure
            measure_details = {}
            for measure_name in measures:
                info = model.measures.get_measure_info(measure_name)
                measure_details[measure_name] = info

            result[name] = {
                'measures': list(measures.keys()),
                'count': len(measures),
                'details': measure_details,
            }

        except Exception as e:
            result[name] = {
                'error': str(e),
                'measures': [],
                'count': 0,
            }

    return result


def discover_parameters(model_name: str, measure_name: str, backend: str = 'duckdb') -> Dict[str, Any]:
    """
    Discover available parameters for a measure.

    Args:
        model_name: Model name
        measure_name: Measure name
        backend: Backend to use (default: 'duckdb')

    Returns:
        Dictionary with parameter information

    Example:
        params = discover_parameters('equity', 'avg_close_price')
        print(f"Required: {params['required']}")
        print(f"Optional: {params['optional']}")
    """
    ctx = RepoContext.from_repo_root(connection_type=backend)
    session = UniversalSession(
        connection=ctx.connection,
        storage_cfg=ctx.storage,
        repo_root=ctx.repo
    )

    try:
        model = session.get_model_instance(model_name)
        measure_info = model.measures.get_measure_info(measure_name)

        # Common parameters for all measures
        common_params = {
            'tickers': {
                'type': 'list[str] or str',
                'description': 'Filter by ticker symbol(s)',
                'example': ['AAPL', 'MSFT'],
                'required': False,
            },
            'start_date': {
                'type': 'str',
                'description': 'Start date for filtering (YYYY-MM-DD)',
                'example': '2024-01-01',
                'required': False,
            },
            'end_date': {
                'type': 'str',
                'description': 'End date for filtering (YYYY-MM-DD)',
                'example': '2024-12-31',
                'required': False,
            },
            'entity_column': {
                'type': 'str',
                'description': 'Column to group by',
                'example': 'ticker',
                'required': False,
            },
            'limit': {
                'type': 'int',
                'description': 'Maximum number of results',
                'example': 10,
                'required': False,
            },
        }

        # Measure-specific parameters
        measure_params = {}

        # Extract parameters from measure config
        if 'group_by' in measure_info:
            group_by = measure_info['group_by']
            if group_by:
                measure_params['group_by'] = {
                    'type': 'list[str]',
                    'description': f'Grouping columns (default: {group_by})',
                    'example': group_by,
                    'required': False,
                }

        if 'weighting_method' in measure_info:
            measure_params['weighting_method'] = {
                'type': 'str',
                'description': 'Weighting strategy',
                'example': measure_info['weighting_method'],
                'required': False,
                'options': [
                    'equal', 'volume', 'market_cap', 'price',
                    'volume_deviation', 'volatility'
                ],
            }

        return {
            'model': model_name,
            'measure': measure_name,
            'measure_type': measure_info.get('type', 'unknown'),
            'source': measure_info.get('source', 'unknown'),
            'required': ['model', 'measure'],
            'optional': {**common_params, **measure_params},
            'measure_info': measure_info,
        }

    except Exception as e:
        return {
            'error': str(e),
            'model': model_name,
            'measure': measure_name,
        }


def list_models(backend: str = 'duckdb') -> List[str]:
    """
    List all available models.

    Args:
        backend: Backend to use (default: 'duckdb')

    Returns:
        List of model names

    Example:
        models = list_models()
        print(f"Available models: {models}")
    """
    ctx = RepoContext.from_repo_root(connection_type=backend)
    session = UniversalSession(
        connection=ctx.connection,
        storage_cfg=ctx.storage,
        repo_root=ctx.repo
    )
    return list(session.registry.models.keys())


def list_weighting_strategies() -> Dict[str, str]:
    """
    List available weighting strategies.

    Returns:
        Dictionary mapping strategy name to description

    Example:
        strategies = list_weighting_strategies()
        for name, desc in strategies.items():
            print(f"{name}: {desc}")
    """
    return {
        'equal': 'Equal weighting - simple average (all weights equal)',
        'volume': 'Volume-weighted - higher trading volume = higher weight',
        'market_cap': 'Market cap weighted - larger companies = higher weight (like S&P 500)',
        'price': 'Price-weighted - higher price = higher weight (like DJIA)',
        'volume_deviation': 'Volume deviation - unusual trading activity = higher weight',
        'volatility': 'Volatility-weighted - inverse volatility for risk-adjusted weights',
    }


def get_example_params(model_name: str, measure_name: str) -> Dict[str, Any]:
    """
    Get example parameters for a measure.

    Args:
        model_name: Model name
        measure_name: Measure name

    Returns:
        Dictionary with example parameters

    Example:
        example = get_example_params('equity', 'volume_weighted_index')
        print(example)
    """
    # Common examples
    examples = {
        'equity': {
            'avg_close_price': {
                'model': 'equity',
                'measure': 'avg_close_price',
                'tickers': ['AAPL', 'MSFT', 'GOOGL'],
                'start_date': '2024-01-01',
                'end_date': '2024-12-31',
                'entity_column': 'ticker',
                'limit': 10,
            },
            'volume_weighted_index': {
                'model': 'equity',
                'measure': 'volume_weighted_index',
                'tickers': ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA'],
                'start_date': '2024-01-01',
                'end_date': '2024-12-31',
            },
            'total_volume': {
                'model': 'equity',
                'measure': 'total_volume',
                'tickers': ['AAPL'],
                'start_date': '2024-01-01',
                'end_date': '2024-12-31',
                'entity_column': 'ticker',
            },
        },
        'corporate': {
            'avg_market_cap': {
                'model': 'corporate',
                'measure': 'avg_market_cap',
                'entity_column': 'company_name',
                'limit': 20,
            },
        },
        'macro': {
            'avg_unemployment_rate': {
                'model': 'macro',
                'measure': 'avg_unemployment_rate',
                'start_date': '2020-01-01',
                'end_date': '2024-12-31',
            },
        },
    }

    # Return specific example if available
    if model_name in examples and measure_name in examples[model_name]:
        return examples[model_name][measure_name]

    # Otherwise return generic example
    return {
        'model': model_name,
        'measure': measure_name,
        'tickers': ['AAPL', 'MSFT'],
        'start_date': '2024-01-01',
        'end_date': '2024-12-31',
        'limit': 10,
    }


def print_measure_catalog(backend: str = 'duckdb') -> None:
    """
    Print a formatted catalog of all measures.

    Args:
        backend: Backend to use (default: 'duckdb')

    Example:
        print_measure_catalog()
    """
    measures = discover_measures(backend=backend)

    print("=" * 80)
    print("MEASURE CATALOG")
    print("=" * 80)

    for model_name, model_info in measures.items():
        if 'error' in model_info:
            print(f"\n{model_name}: Error - {model_info['error']}")
            continue

        print(f"\n{model_name.upper()} ({model_info['count']} measures)")
        print("-" * 80)

        for measure_name, details in model_info['details'].items():
            print(f"\n  {measure_name}")
            print(f"    Type: {details.get('type', 'unknown')}")
            print(f"    Source: {details.get('source', 'unknown')}")
            if 'data_type' in details:
                print(f"    Data Type: {details['data_type']}")
            if 'weighting_method' in details:
                print(f"    Weighting: {details['weighting_method']}")

    print("\n" + "=" * 80)


def print_parameter_help(model_name: str, measure_name: str) -> None:
    """
    Print formatted parameter help for a measure.

    Args:
        model_name: Model name
        measure_name: Measure name

    Example:
        print_parameter_help('equity', 'volume_weighted_index')
    """
    params = discover_parameters(model_name, measure_name)

    if 'error' in params:
        print(f"Error: {params['error']}")
        return

    print("=" * 80)
    print(f"PARAMETER HELP: {model_name}.{measure_name}")
    print("=" * 80)

    print(f"\nMeasure Type: {params['measure_type']}")
    print(f"Source: {params['source']}")

    print("\nREQUIRED PARAMETERS:")
    for param in params['required']:
        print(f"  - {param}")

    print("\nOPTIONAL PARAMETERS:")
    for param_name, param_info in params['optional'].items():
        print(f"\n  {param_name}")
        print(f"    Type: {param_info['type']}")
        print(f"    Description: {param_info['description']}")
        print(f"    Example: {param_info['example']}")
        if 'options' in param_info:
            print(f"    Options: {', '.join(param_info['options'])}")

    # Print example usage
    example = get_example_params(model_name, measure_name)
    print("\nEXAMPLE USAGE:")
    print("  from scripts.examples.parameter_interface import MeasureCalculator")
    print("  calc = MeasureCalculator()")
    print(f"  result = calc.calculate({example})")
    print("  print(result.data)")

    print("\n" + "=" * 80)
