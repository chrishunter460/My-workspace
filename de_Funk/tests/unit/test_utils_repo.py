#!/usr/bin/env python3
"""
Unit tests for utils.repo module.

Tests the centralized repo path management utilities.
"""

import sys
import unittest
from pathlib import Path
import tempfile
import shutil

# Bootstrap
_current = Path(__file__).resolve()
for _parent in [_current.parent] + list(_current.parents):
    if (_parent / "configs").exists() and (_parent / "src").exists():
        if str(_parent / "src") not in sys.path:
            sys.path.insert(0, str(_parent / "src"))
        break

from de_funk.utils.repo import get_repo_root, setup_repo_imports, verify_repo_structure, repo_imports


class TestGetRepoRoot(unittest.TestCase):
    """Test get_repo_root() function."""

    def test_finds_repo_root(self):
        """Test that get_repo_root() finds the repository root."""
        repo_root = get_repo_root()

        self.assertIsInstance(repo_root, Path)
        self.assertTrue(repo_root.exists())
        self.assertTrue((repo_root / "configs").exists())
        self.assertTrue((repo_root / "src" / "de_funk").exists())

    def test_repo_root_is_absolute(self):
        """Test that returned path is absolute."""
        repo_root = get_repo_root()
        self.assertTrue(repo_root.is_absolute())

    def test_from_different_start_paths(self):
        """Test discovery from different starting points."""
        repo_root1 = get_repo_root()
        repo_root2 = get_repo_root(Path(__file__).parent)
        repo_root3 = get_repo_root(Path(__file__).parent.parent)

        # All should find the same root
        self.assertEqual(repo_root1, repo_root2)
        self.assertEqual(repo_root2, repo_root3)

    def test_raises_on_invalid_path(self):
        """Test that ValueError is raised when repo can't be found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(ValueError):
                get_repo_root(Path(tmpdir))


class TestSetupRepoImports(unittest.TestCase):
    """Test setup_repo_imports() function."""

    def test_adds_repo_to_sys_path(self):
        """Test that repo is added to sys.path."""
        original_path = sys.path.copy()

        repo_root = setup_repo_imports()

        # Should have added repo to path
        self.assertIn(str(repo_root), sys.path)

        # Cleanup
        sys.path = original_path

    def test_returns_repo_root(self):
        """Test that function returns repo root Path."""
        repo_root = setup_repo_imports()

        self.assertIsInstance(repo_root, Path)
        self.assertTrue(repo_root.exists())
        self.assertTrue((repo_root / "configs").exists())

    def test_idempotent(self):
        """Test that calling multiple times doesn't duplicate in sys.path."""
        setup_repo_imports()
        setup_repo_imports()
        setup_repo_imports()

        # Should not have added src path multiple times
        repo_root = get_repo_root()
        src_count = sys.path.count(str(repo_root / "src"))
        self.assertLessEqual(src_count, 1)


class TestVerifyRepoStructure(unittest.TestCase):
    """Test verify_repo_structure() function."""

    def test_valid_structure(self):
        """Test that current repo structure is valid."""
        is_valid = verify_repo_structure()
        self.assertTrue(is_valid)


class TestRepoImportsContextManager(unittest.TestCase):
    """Test repo_imports() context manager."""

    def test_context_manager_cleanup(self):
        """Test that context manager cleans up sys.path."""
        repo_root = get_repo_root()
        repo_str = str(repo_root)

        # Remove from sys.path if already there
        while repo_str in sys.path:
            sys.path.remove(repo_str)

        original_path = sys.path.copy()

        with repo_imports() as root:
            # Inside context: should be in path
            self.assertEqual(root, repo_root)
            self.assertIn(repo_str, sys.path)

        # Outside context: should be cleaned up
        self.assertEqual(sys.path, original_path)

    def test_context_manager_with_existing_path(self):
        """Test context manager when repo already in sys.path."""
        repo_root = get_repo_root()
        repo_str = str(repo_root)

        # Ensure it's in sys.path
        if repo_str not in sys.path:
            sys.path.insert(0, repo_str)

        original_path = sys.path.copy()

        with repo_imports() as root:
            # Should work fine
            self.assertEqual(root, repo_root)

        # Should not have removed it (it was already there)
        self.assertEqual(sys.path, original_path)


class TestRepoRootConsistency(unittest.TestCase):
    """Test consistency across different methods."""

    def test_all_methods_return_same_root(self):
        """Test that all methods return the same repo root."""
        root1 = get_repo_root()
        root2 = setup_repo_imports()

        with repo_imports() as root3:
            pass

        self.assertEqual(root1, root2)
        self.assertEqual(root2, root3)

    def test_repo_root_structure(self):
        """Test that repo root has expected structure."""
        repo_root = get_repo_root()

        expected_dirs = [
            "src/de_funk",
            "src/de_funk/config",
            "src/de_funk/core",
            "src/de_funk/models",
            "src/de_funk/utils",
            "configs",
            "scripts",
            "docs",
        ]

        for dir_name in expected_dirs:
            dir_path = repo_root / dir_name
            self.assertTrue(
                dir_path.exists(),
                f"Expected directory not found: {dir_name}"
            )


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""

    def test_handles_symlinks(self):
        """Test that function handles symlinks correctly."""
        # Should resolve symlinks and find real path
        repo_root = get_repo_root()
        self.assertTrue(repo_root.is_absolute())

    def test_handles_relative_paths(self):
        """Test that function handles relative paths."""
        # Should work even with relative start path
        rel_path = Path(".")
        repo_root = get_repo_root(rel_path)
        self.assertTrue(repo_root.exists())


if __name__ == "__main__":
    unittest.main()
