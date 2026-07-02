#!/usr/bin/env python3
"""
Validate notebook references against domain markdown configs.

Checks that all model.table references in notebooks exist in the
domain configuration files.

Usage:
    python -m scripts.test.validate_notebook_references
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()


def extract_table_references(notebook_path: Path) -> List[Tuple[str, str, int]]:
    """
    Extract model.table references from a notebook.

    Returns list of (model, table, line_number) tuples.
    """
    content = notebook_path.read_text()
    references = []

    # Pattern for source: model.table
    source_pattern = re.compile(r'source:\s*(\w+)\.(\w+)')

    # Pattern for source: {model: X, table: Y}
    dict_pattern = re.compile(r'source:\s*\{[^}]*model:\s*(\w+)[^}]*table:\s*(\w+)')

    for i, line in enumerate(content.split('\n'), 1):
        for match in source_pattern.finditer(line):
            references.append((match.group(1), match.group(2), i))
        for match in dict_pattern.finditer(line):
            references.append((match.group(1), match.group(2), i))

    return references


def get_domain_tables(domains_dir: Path) -> Dict[str, Set[str]]:
    """
    Get all tables defined in domain markdown files.

    Returns dict of model_name -> set of table names.
    """
from de_funk.models.registry import ModelRegistry

    registry = ModelRegistry(domains_dir)
    model_tables = {}

    for model_name in registry.list_models():
        try:
            model = registry.get_model(model_name)
            tables = set(model.list_tables())
            model_tables[model_name] = tables
        except Exception as e:
            print(f"Warning: Could not load model '{model_name}': {e}")

    return model_tables


def validate_notebooks(notebooks_dir: Path, domains_dir: Path) -> List[dict]:
    """
    Validate all notebooks against domain configs.

    Returns list of validation errors.
    """
    errors = []

    # Get all tables from domain configs
    model_tables = get_domain_tables(domains_dir)
    available_models = set(model_tables.keys())

    print(f"\nAvailable models: {sorted(available_models)}")
    print(f"\nTables per model:")
    for model, tables in sorted(model_tables.items()):
        print(f"  {model}: {sorted(tables)}")

    print("\n" + "=" * 60)
    print("Validating notebook references...")
    print("=" * 60)

    # Check each notebook
    for notebook_path in notebooks_dir.rglob('*.md'):
        refs = extract_table_references(notebook_path)
        if not refs:
            continue

        print(f"\n{notebook_path.relative_to(notebooks_dir)}:")

        seen = set()
        for model, table, line_num in refs:
            ref_key = f"{model}.{table}"
            if ref_key in seen:
                continue
            seen.add(ref_key)

            if model not in available_models:
                errors.append({
                    'notebook': str(notebook_path.name),
                    'line': line_num,
                    'model': model,
                    'table': table,
                    'error': f"Model '{model}' not found"
                })
                print(f"  ❌ Line {line_num}: {model}.{table} - Model not found!")
            elif table not in model_tables.get(model, set()):
                errors.append({
                    'notebook': str(notebook_path.name),
                    'line': line_num,
                    'model': model,
                    'table': table,
                    'error': f"Table '{table}' not in model '{model}'"
                })
                available = sorted(model_tables.get(model, []))
                print(f"  ❌ Line {line_num}: {model}.{table} - Table not found!")
                print(f"      Available tables in '{model}': {available}")
            else:
                print(f"  ✓ {model}.{table}")

    return errors


def main():
    print("=" * 60)
    print("  Notebook Reference Validation")
    print("=" * 60)

    notebooks_dir = repo_root / "configs" / "notebooks"
    domains_dir = repo_root / "domains"

    if not notebooks_dir.exists():
        print(f"ERROR: Notebooks directory not found: {notebooks_dir}")
        sys.exit(1)

    if not domains_dir.exists():
        print(f"ERROR: Domains directory not found: {domains_dir}")
        sys.exit(1)

    errors = validate_notebooks(notebooks_dir, domains_dir)

    print("\n" + "=" * 60)
    if errors:
        print(f"  VALIDATION FAILED: {len(errors)} errors found")
        print("=" * 60)
        print("\nErrors Summary:")
        for err in errors:
            print(f"  - {err['notebook']} line {err['line']}: {err['error']}")
        sys.exit(1)
    else:
        print("  VALIDATION PASSED: All references valid")
        print("=" * 60)
        sys.exit(0)


if __name__ == "__main__":
    main()
