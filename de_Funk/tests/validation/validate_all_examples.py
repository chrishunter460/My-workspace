#!/usr/bin/env python3
"""
Validation script for all example files.

This script attempts to import all Python example files to ensure they have no
syntax errors and can be loaded successfully. It provides a quick sanity check
for the examples before running full integration tests.

Usage:
    python scripts/test/validation/validate_all_examples.py
    python -m scripts.test.validation.validate_all_examples
"""

import sys
from pathlib import Path
from typing import List, Tuple
import importlib.util


def get_repo_root() -> Path:
    """Get repository root directory."""
    current = Path(__file__).resolve()
    while current.parent != current:
        if (current / '.git').exists() or (current / 'configs').exists():
            return current
        current = current.parent
    return Path.cwd()


def find_example_files(examples_dir: Path) -> List[Path]:
    """Find all Python example files (excluding __init__.py)."""
    python_files = []

    # Search in all subdirectories
    for subdir in examples_dir.iterdir():
        if subdir.is_dir() and not subdir.name.startswith('_'):
            python_files.extend([
                f for f in subdir.glob('*.py')
                if f.name != '__init__.py'
            ])

    return sorted(python_files)


def import_module_from_path(file_path: Path) -> Tuple[bool, str]:
    """
    Attempt to import a module from a file path.

    Returns:
        Tuple of (success: bool, error_message: str)
    """
    try:
        # Create module name from path
        module_name = file_path.stem

        # Load the module
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            return False, "Could not create module spec"

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        return True, ""

    except Exception as e:
        return False, str(e)


def validate_examples() -> Tuple[int, int, List[str]]:
    """
    Validate all example files can be imported.

    Returns:
        Tuple of (success_count, failure_count, error_messages)
    """
    repo_root = get_repo_root()
    examples_dir = repo_root / 'scripts' / 'examples'

    if not examples_dir.exists():
        print(f"❌ Examples directory not found: {examples_dir}")
        return 0, 0, ["Examples directory not found"]

    print(f"🔍 Searching for examples in: {examples_dir}")
    example_files = find_example_files(examples_dir)

    if not example_files:
        print("⚠️  No example files found")
        return 0, 0, ["No example files found"]

    print(f"📝 Found {len(example_files)} example files\n")

    success_count = 0
    failure_count = 0
    error_messages = []

    for file_path in example_files:
        relative_path = file_path.relative_to(repo_root)
        print(f"  Testing: {relative_path}...", end=" ")

        success, error = import_module_from_path(file_path)

        if success:
            print("✅")
            success_count += 1
        else:
            print("❌")
            failure_count += 1
            error_msg = f"{relative_path}: {error}"
            error_messages.append(error_msg)

    return success_count, failure_count, error_messages


def main():
    """Main validation function."""
    print("=" * 70)
    print("Example Files Validation")
    print("=" * 70)
    print()

    success_count, failure_count, error_messages = validate_examples()

    print()
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"✅ Passed: {success_count}")
    print(f"❌ Failed: {failure_count}")
    print()

    if error_messages:
        print("Errors:")
        print("-" * 70)
        for error in error_messages:
            print(f"  • {error}")
        print()
        return 1

    print("🎉 All examples validated successfully!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
