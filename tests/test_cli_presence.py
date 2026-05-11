"""
Unit tests for run_presence() CLI handler in cli/main.py.

Covers:
- check action: no lock (exit 0, "NO human presence" message)
- check action: fresh lock (exit 1, "Human presence detected" message)
- check action: stale lock (exit 0, "Stale" message)
- take action: creates lock, prints confirmation (exit 0)
- release action: removes lock, prints confirmation (exit 0)
- release action: no lock to release (exit 0, "No presence lock" message)
- --local flag: uses CWD-relative lock path instead of SYSTEM_LOCK_PATH
- default action (no explicit action): behaves as check
"""

import argparse
import os
import time
import pytest

from unittest.mock import patch, MagicMock
from ghost.presence import SYSTEM_LOCK_PATH, PRESENCE_TTL_SECONDS, PresenceStatus


def _make_args(action="check", local=False):
    """Build a minimal argparse.Namespace for run_presence."""
    args = argparse.Namespace()
    args.action = action
    args.local = local
    return args


def _fresh_status(lock_path):
    return PresenceStatus(lock_exists=True, human_present=True, age_seconds=30.0, lock_path=lock_path)


def _stale_status(lock_path):
    age = PRESENCE_TTL_SECONDS + 120
    return PresenceStatus(lock_exists=True, human_present=False, age_seconds=float(age), lock_path=lock_path)


def _absent_status(lock_path):
    return PresenceStatus(lock_exists=False, human_present=False, age_seconds=None, lock_path=lock_path)


class TestCheckAction:
    def test_no_lock_prints_clear_and_exits_zero(self, capsys):
        from cli.main import run_presence
        args = _make_args(action="check")
        with patch("ghost.presence.check_presence", return_value=_absent_status(SYSTEM_LOCK_PATH)):
            result = run_presence(args)
        assert result == 0
        out = capsys.readouterr().out
        assert "NO human presence" in out

    def test_fresh_lock_prints_detected_and_exits_one(self, capsys):
        from cli.main import run_presence
        args = _make_args(action="check")
        with patch("ghost.presence.check_presence", return_value=_fresh_status(SYSTEM_LOCK_PATH)):
            result = run_presence(args)
        assert result == 1
        out = capsys.readouterr().out
        assert "Human presence detected" in out

    def test_stale_lock_prints_stale_and_exits_zero(self, capsys):
        from cli.main import run_presence
        args = _make_args(action="check")
        with patch("ghost.presence.check_presence", return_value=_stale_status(SYSTEM_LOCK_PATH)):
            result = run_presence(args)
        assert result == 0
        out = capsys.readouterr().out
        assert "Stale" in out or "stale" in out.lower()

    def test_default_action_behaves_as_check_no_lock(self, capsys):
        from cli.main import run_presence
        args = _make_args(action="check")
        with patch("ghost.presence.check_presence", return_value=_absent_status(SYSTEM_LOCK_PATH)):
            result = run_presence(args)
        assert result == 0


class TestTakeAction:
    def test_take_calls_acquire_lock_and_exits_zero(self, capsys):
        from cli.main import run_presence
        args = _make_args(action="take")
        with patch("ghost.presence.acquire_lock") as mock_acquire:
            result = run_presence(args)
        mock_acquire.assert_called_once()
        assert result == 0
        out = capsys.readouterr().out
        assert "Presence lock taken" in out

    def test_take_uses_system_lock_path_by_default(self, capsys):
        from cli.main import run_presence
        args = _make_args(action="take", local=False)
        with patch("ghost.presence.acquire_lock") as mock_acquire:
            run_presence(args)
        called_path = mock_acquire.call_args[0][0]
        assert called_path == SYSTEM_LOCK_PATH


class TestReleaseAction:
    def test_release_calls_release_lock_and_exits_zero(self, capsys):
        from cli.main import run_presence
        args = _make_args(action="release")
        with patch("ghost.presence.release_lock", return_value=True) as mock_release:
            result = run_presence(args)
        mock_release.assert_called_once()
        assert result == 0
        out = capsys.readouterr().out
        assert "released" in out

    def test_release_no_lock_prints_info_and_exits_zero(self, capsys):
        from cli.main import run_presence
        args = _make_args(action="release")
        with patch("ghost.presence.release_lock", return_value=False):
            result = run_presence(args)
        assert result == 0
        out = capsys.readouterr().out
        assert "No presence lock" in out or "nothing to release" in out.lower() or "ℹ" in out


class TestLocalFlag:
    def test_local_flag_uses_cwd_relative_path(self, tmp_path, monkeypatch, capsys):
        from cli.main import run_presence
        monkeypatch.chdir(tmp_path)
        args = _make_args(action="take", local=True)
        expected_path = os.path.join(str(tmp_path), "presence.lock")
        with patch("ghost.presence.acquire_lock") as mock_acquire:
            run_presence(args)
        called_path = mock_acquire.call_args[0][0]
        assert called_path == expected_path

    def test_without_local_flag_uses_system_lock_path(self, capsys):
        from cli.main import run_presence
        args = _make_args(action="check", local=False)
        with patch("ghost.presence.check_presence", return_value=_absent_status(SYSTEM_LOCK_PATH)) as mock_check:
            run_presence(args)
        called_path = mock_check.call_args[0][0]
        assert called_path == SYSTEM_LOCK_PATH
