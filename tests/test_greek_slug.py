"""
Regression tests for kingdonb/mecris#128.

Guard: Greek Beeminder goal slug must always be 'ellinika', never 'reviewstack-greek'.

Context: The issue was opened to correct the Greek slug. All active code was already
using 'ellinika' correctly; 'reviewstack-greek' appears only in docs/ as a proposed
future goal name for a separate backlog-tracking goal. These tests prevent regression.
"""
import pathlib
import pytest
from unittest.mock import MagicMock

CORRECT_GREEK_SLUG = "ellinika"


def test_language_sync_service_greek_not_automated(monkeypatch):
    """LanguageSyncService must not automate Greek Beeminder pushes (it's an odometer)."""
    monkeypatch.setenv("NEON_DB_URL", "postgres://fake")
    from services.language_sync_service import LanguageSyncService

    service = LanguageSyncService(beeminder_client=MagicMock())
    assert "GREEK" not in service.lang_to_slug, "GREEK should not be in lang_to_slug"


def test_no_active_python_code_uses_reviewstack_greek():
    """
    No active Python source file should contain 'reviewstack-greek' as a hardcoded value.
    The only sanctioned uses are in docs/ planning files (not Python code).
    """
    root = pathlib.Path(__file__).parent.parent
    python_files = root.glob("**/*.py")

    violations = []
    # Project-level directories to skip for speed and accuracy
    SKIP_DIRS = {".venv", ".git", "__pycache__", "node_modules", "attic", ".claude", ".gemini", ".mcp"}
    
    for f in python_files:
        # Check if any part of the path is in our skip list
        if any(part in SKIP_DIRS for part in f.parts):
            continue
            
        # Skip self — this file contains the banned string in docstrings/comments
        if f.name == "test_greek_slug.py":
            continue
        try:
            if "reviewstack-greek" in f.read_text():
                violations.append(str(f.relative_to(root)))
        except Exception:
            pass

    assert violations == [], (
        f"Found 'reviewstack-greek' in active Python files (should only appear in docs/): {violations}"
    )
