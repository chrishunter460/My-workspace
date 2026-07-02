"""
Centralized repository path and import management.

This module provides utilities for finding the repo root and setting up
Python import paths, eliminating the need for manual path manipulation
in every script.

Usage:
    # Option 1: Just get the repo root (no sys.path modification)
    from de_funk.utils.repo import get_repo_root
    repo_root = get_repo_root()

    # Option 2: Auto-setup imports (recommended for scripts)
    from de_funk.utils.repo import setup_repo_imports
    repo_root = setup_repo_imports()
    # Now you can import from anywhere in the repo!

    # Option 3: Use with context manager (auto-cleanup)
    from de_funk.utils.repo import repo_imports
    with repo_imports() as repo_root:
        from de_funk.core.context import RepoContext
        # ... your code ...
"""

import sys
from pathlib import Path
from typing import Optional, List
from contextlib import contextmanager


# Markers used to identify the repository root
REPO_MARKERS = ["src", "configs", ".git"]


def get_repo_root(start_path: Optional[Path] = None) -> Path:
    """
    Find repository root by walking up from start_path.

    This is the single source of truth for repo root discovery.
    Uses markers (src/, configs/, .git/) to identify the root.

    Args:
        start_path: Starting path for search. If None, starts from this file's location.

    Returns:
        Path to repository root.

    Raises:
        ValueError: If repo root cannot be found.

    Example:
        >>> repo_root = get_repo_root()
        >>> print(repo_root)
        /home/user/de_Funk
    """
    # Start from this file's location if no path provided
    # This ensures it works even when called from deeply nested scripts
    if start_path is None:
        # src/de_funk/utils/ -> src/de_funk/ -> src/ -> repo/
        start_path = Path(__file__).resolve().parent.parent.parent.parent

    current = Path(start_path).resolve()

    # Walk up directory tree
    for parent in [current] + list(current.parents):
        # Check if this directory contains all markers
        if all((parent / marker).exists() for marker in REPO_MARKERS):
            return parent

    # Fallback: check if current directory itself is the repo
    if all((current / marker).exists() for marker in REPO_MARKERS):
        return current

    raise ValueError(
        f"Could not find repository root from {start_path}. "
        f"Looking for directories containing: {', '.join(REPO_MARKERS)}"
    )


def setup_repo_imports(start_path: Optional[Path] = None) -> Path:
    """
    Find repo root and add it to sys.path for imports.

    This is the recommended way to set up imports in scripts. It:
    - Finds the repo root reliably
    - Adds repo_root/src to sys.path for de_funk.* imports
    - Returns the repo root path for further use

    Args:
        start_path: Starting path for search. If None, auto-detects.

    Returns:
        Path to repository root.

    Example:
        # At the top of your script:
        from de_funk.utils.repo import setup_repo_imports
        repo_root = setup_repo_imports()

        # Now you can import from the de_funk package:
        from de_funk.core.context import RepoContext
    """
    repo_root = get_repo_root(start_path)

    # Add src/ to sys.path for de_funk.* imports
    src_path = str(repo_root / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    # Also add repo root for backwards compatibility with app/ imports
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)

    return repo_root


@contextmanager
def repo_imports(start_path: Optional[Path] = None):
    """
    Context manager for temporary repo imports.

    Adds repo/src to sys.path for the duration of the context,
    then removes it when exiting. Useful for scripts that
    need imports but want to clean up after themselves.

    Args:
        start_path: Starting path for search. If None, auto-detects.

    Yields:
        Path to repository root.

    Example:
        from de_funk.utils.repo import repo_imports

        with repo_imports() as repo_root:
            from de_funk.core.context import RepoContext
            ctx = RepoContext.from_repo_root()
            # ... your code ...
        # sys.path is restored after exiting
    """
    repo_root = get_repo_root(start_path)
    src_path = str(repo_root / "src")
    repo_root_str = str(repo_root)

    # Track if we added them (only remove if we added them)
    added_src = False
    added_root = False

    if src_path not in sys.path:
        sys.path.insert(0, src_path)
        added_src = True
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)
        added_root = True

    try:
        yield repo_root
    finally:
        # Remove from sys.path if we added them
        if added_src and src_path in sys.path:
            sys.path.remove(src_path)
        if added_root and repo_root_str in sys.path:
            sys.path.remove(repo_root_str)


def verify_repo_structure() -> bool:
    """
    Verify that the repository has the expected structure.

    Checks for required directories and files. Useful for
    debugging or validating the environment.

    Returns:
        True if structure is valid, False otherwise.

    Example:
        from de_funk.utils.repo import verify_repo_structure
        if not verify_repo_structure():
            print("ERROR: Invalid repository structure!")
    """
    try:
        repo_root = get_repo_root()

        # Required directories
        required_dirs = [
            "src/de_funk",
            "src/de_funk/config",
            "src/de_funk/core",
            "src/de_funk/models",
            "src/de_funk/utils",
            "configs",
            "scripts",
        ]

        # Check each directory
        missing = []
        for dir_name in required_dirs:
            if not (repo_root / dir_name).exists():
                missing.append(dir_name)

        if missing:
            print(f"WARNING: Missing directories: {', '.join(missing)}")
            return False

        return True

    except ValueError as e:
        print(f"ERROR: Could not verify structure: {e}")
        return False


# Convenience function for backwards compatibility with old patterns
def repo_root_for_script(script_file: str) -> Path:
    """
    Get repo root for a specific script file.

    DEPRECATED: Use get_repo_root() instead. This function is kept
    for backward compatibility with scripts that pass __file__.

    Args:
        script_file: The __file__ variable from the calling script.

    Returns:
        Path to repository root.

    Example (deprecated):
        from de_funk.utils.repo import repo_root_for_script
        repo_root = repo_root_for_script(__file__)

    Recommended:
        from de_funk.utils.repo import get_repo_root
        repo_root = get_repo_root()
    """
    import warnings
    warnings.warn(
        "repo_root_for_script(__file__) is deprecated. "
        "Use get_repo_root() instead (no arguments needed).",
        DeprecationWarning,
        stacklevel=2
    )
    return get_repo_root(Path(script_file).parent)
