"""
Test script to verify environment variable loading and credential injection
"""
from de_funk.utils.env_loader import inject_credentials_into_config
from de_funk.utils.repo import get_repo_root
from pathlib import Path
import json

# Load Alpha Vantage config from correct location
repo_root = get_repo_root()
alpha_vantage_cfg = json.loads((repo_root / "configs" / "alpha_vantage_endpoints.json").read_text())
storage = json.loads((repo_root / "configs" / "storage.json").read_text())

print("=" * 70)
print("BEFORE INJECTION:")
print("=" * 70)
print(f"API Keys: {alpha_vantage_cfg['credentials']['api_keys']}")
print(f"Base URL: {alpha_vantage_cfg['base_urls']['core']}")
print()

# Inject credentials from environment
alpha_vantage_cfg = inject_credentials_into_config(alpha_vantage_cfg, 'alpha_vantage')

print("=" * 70)
print("AFTER INJECTION:")
print("=" * 70)
print(f"API Keys: {alpha_vantage_cfg['credentials']['api_keys']}")
print(f"Number of keys: {len(alpha_vantage_cfg['credentials']['api_keys'])}")

if alpha_vantage_cfg['credentials']['api_keys']:
    first_key = alpha_vantage_cfg['credentials']['api_keys'][0]
    print(f"First key (partial): {first_key[:15]}...")
    print(f"✓ Credentials successfully loaded from .env file!")
else:
    print("✗ No API keys loaded - check your .env file")

print()
print("=" * 70)
print("FULL CONFIG:")
print("=" * 70)
print(json.dumps(alpha_vantage_cfg, indent=2))
