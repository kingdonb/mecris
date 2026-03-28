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


def test_language_sync_service_greek_slug(monkeypatch):
    """LanguageSyncService.lang_to_slug must map GREEK to 'ellinika'."""
    monkeypatch.setenv("NEON_DB_URL", "postgres://fake")
    from services.language_sync_service import LanguageSyncService

    service = LanguageSyncService(beeminder_client=MagicMock())
    assert service.lang_to_slug.get("GREEK") == CORRECT_GREEK_SLUG, (
        f"Expected GREEK slug '{CORRECT_GREEK_SLUG}', got '{service.lang_to_slug.get('GREEK')}'"
    )


def test_language_sync_service_greek_slug_not_reviewstack_greek(monkeypatch):
    """GREEK slug must not be the legacy/wrong 'reviewstack-greek' value."""
    monkeypatch.setenv("NEON_DB_URL", "postgres://fake")
    from services.language_sync_service import LanguageSyncService

    service = LanguageSyncService(beeminder_client=MagicMock())
    assert service.lang_to_slug.get("GREEK") != "reviewstack-greek"


def test_no_active_python_code_uses_reviewstack_greek():
    """
    No active Python source file should contain 'reviewstack-greek' as a hardcoded value.
    The only sanctioned uses are in docs/ planning files (not Python code).
    """
    root = pathlib.Path(__file__).parent.parent
    python_files = root.glob("**/*.py")

    violations = []
    for f in python_files:
        # Skip attic/ — legacy/archived scripts are exempt
        if "attic" in f.parts:
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
