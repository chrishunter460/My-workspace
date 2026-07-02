"""
Extends resolution and deep merge for domain v4 configs.

Handles:
- Dot notation resolution (e.g., _base.property.parcel._dim_parcel)
- Recursive section-level extends
- Deep merge with override semantics
"""

import re
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def parse_front_matter(file_path: Path) -> Dict[str, Any]:
    """
    Parse YAML front matter from a markdown file.

    Args:
        file_path: Path to markdown file

    Returns:
        Parsed YAML dict, or empty dict if no front matter
    """
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return {}

    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}

    try:
        config = yaml.safe_load(match.group(1))
        return config if config else {}
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML in {file_path}: {e}")
        return {}


def deep_merge(base: Dict, override: Dict) -> Dict:
    """
    Deep merge two dictionaries. Override values take precedence.

    - Dicts are recursively merged
    - Lists are replaced, not appended
    - All other values are replaced
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def resolve_extends_reference(
    extends_ref: str,
    domains_dir: Path,
    _cache: Optional[Dict[str, Dict]] = None,
) -> Dict[str, Any]:
    """
    Resolve a dotted extends reference to a config dict.

    Handles formats:
    - "_base.simple.base_template" → file _base/simple/base_template.md
    - "_base.simple.base_template._dim_entity" → file above, navigate to tables._dim_entity

    Args:
        extends_ref: Dotted reference string
        domains_dir: Root domains directory
        _cache: Optional parse cache to avoid re-reading files

    Returns:
        Resolved config dict (or subsection thereof)
    """
    if _cache is None:
        _cache = {}

    parts = extends_ref.split(".")

    # Try progressively longer path prefixes to find the file
    base_config = None
    nav_start_idx = len(parts)  # Default: no navigation needed

    for i in range(len(parts), 0, -1):
        path_parts = parts[:i]
        path_str = "/".join(path_parts)

        # Try as direct file: _base/simple/base_template.md
        file_path = domains_dir / f"{path_str}.md"
        if file_path.exists():
            cache_key = str(file_path)
            if cache_key not in _cache:
                _cache[cache_key] = parse_front_matter(file_path)
            base_config = _cache[cache_key]
            nav_start_idx = i
            break

        # Try as directory with main file: _base/simple/simple.md
        dir_path = domains_dir / path_str
        if dir_path.is_dir():
            main_file = dir_path / f"{path_parts[-1]}.md"
            if main_file.exists():
                cache_key = str(main_file)
                if cache_key not in _cache:
                    _cache[cache_key] = parse_front_matter(main_file)
                base_config = _cache[cache_key]
                nav_start_idx = i
                break

    if base_config is None:
        logger.warning(f"Could not resolve extends: {extends_ref}")
        return {}

    # Navigate into the config if there are remaining path parts
    nav_path = parts[nav_start_idx:]
    if not nav_path:
        return base_config

    # Direct navigation first
    current = base_config
    for nav in nav_path:
        if isinstance(current, dict) and nav in current:
            current = current[nav]
        else:
            current = None
            break

    if current is not None and isinstance(current, dict):
        return current

    # Search common locations for the last part (e.g., table name)
    item_name = nav_path[-1]
    search_paths = [
        ["tables", item_name],
        ["views", item_name],
        ["graph", "nodes", item_name],
        ["schema", "dimensions", item_name],
        ["schema", "facts", item_name],
    ]

    for search_path in search_paths:
        current = base_config
        found = True
        for key in search_path:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                found = False
                break
        if found and isinstance(current, dict):
            return current

    logger.warning(f"Could not navigate to {nav_path} in {extends_ref}")
    return {}


def resolve_nested_extends(
    config: Dict[str, Any],
    domains_dir: Path,
    _cache: Optional[Dict[str, Dict]] = None,
) -> Dict[str, Any]:
    """
    Resolve extends directives in nested structures.

    Handles extends in:
    - tables.{table_name}.extends
    - views.{view_name}.extends
    - graph.extends (section-level)
    - schema.extends (section-level)
    """
    if _cache is None:
        _cache = {}

    # Section-level extends (graph.extends, schema.extends, measures.extends)
    for section in ["graph", "schema", "measures"]:
        if section in config and isinstance(config[section], dict):
            if "extends" in config[section]:
                parent = resolve_extends_reference(
                    config[section]["extends"], domains_dir, _cache
                )
                child = {k: v for k, v in config[section].items() if k != "extends"}
                config[section] = deep_merge(parent, child)

    # Table-level extends
    if "tables" in config and isinstance(config["tables"], dict):
        for table_name, table_config in config["tables"].items():
            if isinstance(table_config, dict) and "extends" in table_config:
                parent = resolve_extends_reference(
                    table_config["extends"], domains_dir, _cache
                )
                child = {k: v for k, v in table_config.items() if k != "extends"}
                config["tables"][table_name] = deep_merge(parent, child)

    # View-level extends
    if "views" in config and isinstance(config["views"], dict):
        for view_name, view_config in config["views"].items():
            if isinstance(view_config, dict) and "extends" in view_config:
                parent = resolve_extends_reference(
                    view_config["extends"], domains_dir, _cache
                )
                child = {k: v for k, v in view_config.items() if k != "extends"}
                config["views"][view_name] = deep_merge(parent, child)

    return config
