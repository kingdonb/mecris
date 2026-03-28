"""
Tests for the Greek Review Backlog Booster (kingdonb/mecris#129).

Validates:
- GREEK_BACKLOG_THRESHOLD constant value
- _greek_backlog_active() threshold boundary (>= 300 → True, < 300 → False)
- Edge cases: missing key, None value
"""

import pytest
from services.language_sync_service import LanguageSyncService, GREEK_BACKLOG_THRESHOLD


def test_threshold_constant():
    assert GREEK_BACKLOG_THRESHOLD == 300


def test_greek_backlog_active_above_threshold():
    lang_stats = {"greek": {"next_7_days": 350}}
    assert LanguageSyncService._greek_backlog_active(lang_stats) is True


def test_greek_backlog_active_at_threshold():
    lang_stats = {"greek": {"next_7_days": 300}}
    assert LanguageSyncService._greek_backlog_active(lang_stats) is True


def test_greek_backlog_active_below_threshold():
    lang_stats = {"greek": {"next_7_days": 250}}
    assert LanguageSyncService._greek_backlog_active(lang_stats) is False


def test_greek_backlog_active_no_greek_key():
    lang_stats = {"arabic": {"next_7_days": 400}}
    assert LanguageSyncService._greek_backlog_active(lang_stats) is False


def test_greek_backlog_active_none_value():
    lang_stats = {"greek": {"next_7_days": None}}
    assert LanguageSyncService._greek_backlog_active(lang_stats) is False


def test_greek_backlog_active_missing_next_7_days():
    lang_stats = {"greek": {"current": 100}}
    assert LanguageSyncService._greek_backlog_active(lang_stats) is False


def test_greek_backlog_active_uppercase_key_fallback():
    """Accepts GREEK (uppercase) as well as greek (lowercase)."""
    lang_stats = {"GREEK": {"next_7_days": 400}}
    assert LanguageSyncService._greek_backlog_active(lang_stats) is True
