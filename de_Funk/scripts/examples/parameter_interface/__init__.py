"""
Parameter-driven calculation interface for de_Funk measures.

This module provides a clean, user-friendly interface for running measure calculations
using parameter dictionaries instead of code.
"""

from .calculator import MeasureCalculator, CalculationRequest, CalculationResult
from .validators import validate_params, ParameterError
from .discovery import discover_measures, discover_parameters

__all__ = [
    'MeasureCalculator',
    'CalculationRequest',
    'CalculationResult',
    'validate_params',
    'ParameterError',
    'discover_measures',
    'discover_parameters',
]
