"""
Environment Variable Loader for de_Funk

DEPRECATED: This module is deprecated in favor of the unified config system.
Please use config.ConfigLoader for new code.

This module is kept for backward compatibility but will be removed in a future version.
Functions are still available but now recommend using the centralized config system.
"""

import os
from pathlib import Path
from typing import List, Optional
import warnings


def find_dotenv(start_path: Optional[Path] = None) -> Optional[Path]:
    """
    Find .env file by walking up from start_path to repo root.

    Args:
        start_path: Starting directory (default: current file's directory)

    Returns:
        Path to .env file if found, None otherwise
    """
    if start_path is None:
        start_path = Path(__file__).resolve().parent

    current = start_path if start_path.is_dir() else start_path.parent

    # Walk up to find repo root (has configs/ and core/ directories)
    while current != current.parent:
        env_file = current / ".env"
        if env_file.exists():
            return env_file

        # Stop at repo root
        if (current / "configs").exists() and (current / "core").exists():
            env_file = current / ".env"
            return env_file if env_file.exists() else None

        current = current.parent

    return None


def load_dotenv(dotenv_path: Optional[Path] = None) -> bool:
    """
    Load environment variables from .env file.

    Args:
        dotenv_path: Path to .env file (default: auto-detect)

    Returns:
        True if .env file was loaded, False otherwise
    """
    if dotenv_path is None:
        dotenv_path = find_dotenv()

    if dotenv_path is None or not dotenv_path.exists():
        return False

    with open(dotenv_path) as f:
        for line in f:
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue

            # Parse KEY=VALUE
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()

                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]

                # Only set if not already in environment
                if key not in os.environ:
                    os.environ[key] = value

    return True


def get_api_keys(env_var: str, fallback: Optional[List[str]] = None) -> List[str]:
    """
    Get API keys from environment variable.

    Supports both comma-separated keys and JSON array format.

    Args:
        env_var: Environment variable name
        fallback: Fallback list of keys if env var not set

    Returns:
        List of API keys
    """
    value = os.getenv(env_var, '').strip()

    if not value:
        if fallback:
            return fallback
        return []

    # Handle comma-separated keys
    if ',' in value:
        return [k.strip() for k in value.split(',') if k.strip()]

    # Single key
    return [value] if value else []


def get_polygon_api_keys() -> List[str]:
    """Get Polygon API keys from environment."""
    keys = get_api_keys('POLYGON_API_KEYS')

    if not keys:
        warnings.warn(
            "POLYGON_API_KEYS not set in environment. "
            "Please set it in .env file or environment. "
            "See .env.example for template.",
            UserWarning
        )

    return keys


def get_bls_api_keys() -> List[str]:
    """Get BLS API keys from environment."""
    keys = get_api_keys('BLS_API_KEYS')

    if not keys:
        warnings.warn(
            "BLS_API_KEYS not set in environment. "
            "BLS API will work with limited rate limits. "
            "For higher limits, register at https://data.bls.gov/registrationEngine/",
            UserWarning
        )

    return keys


def get_chicago_api_keys() -> List[str]:
    """Get Chicago Data Portal app tokens from environment."""
    keys = get_api_keys('CHICAGO_API_KEYS')

    if not keys:
        warnings.warn(
            "CHICAGO_API_KEYS not set in environment. "
            "Chicago Data Portal will work with limited rate limits. "
            "For higher limits, get an app token at https://data.cityofchicago.org/profile/app_tokens",
            UserWarning
        )

    return keys


def inject_credentials_into_config(config: dict, provider: str) -> dict:
    """
    Inject API keys from environment into provider config.

    Args:
        config: Provider configuration dict
        provider: Provider name ('polygon', 'bls', 'chicago')

    Returns:
        Updated config dict with credentials from environment
    """
    config = config.copy()

    # Get API keys based on provider
    if provider == 'polygon':
        api_keys = get_polygon_api_keys()
    elif provider == 'bls':
        api_keys = get_bls_api_keys()
    elif provider == 'chicago':
        api_keys = get_chicago_api_keys()
    else:
        raise ValueError(f"Unknown provider: {provider}")

    # Inject into credentials
    if 'credentials' not in config:
        config['credentials'] = {}

    config['credentials']['api_keys'] = api_keys

    # For backward compatibility with api_validator.py (uses 'api_key' not 'api_keys')
    if provider == 'polygon' and api_keys:
        config['credentials']['api_key'] = api_keys[0]

    return config


# REMOVED: Auto-load on import (caused side effects)
# The new config.ConfigLoader handles .env loading explicitly.
# For backward compatibility, auto-load is now opt-in via environment variable.
if os.getenv("LEGACY_ENV_AUTOLOAD", "").lower() == "true":
    load_dotenv()
    warnings.warn(
        "LEGACY_ENV_AUTOLOAD is deprecated. "
        "Please migrate to config.ConfigLoader for explicit configuration management. "
        "See docs/configuration.md for migration guide.",
        DeprecationWarning,
        stacklevel=2
    )
