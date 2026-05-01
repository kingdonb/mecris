"""
Unit tests for scripts/check_neon_budget.py

This script runs entirely at module level and connects directly to a Neon
database. It has no importable functions. Tests exercise the script via
subprocess with a minimal fake psycopg2 package injected into PYTHONPATH,
so no real database connection is required.

Covers:
  - Missing NEON_DB_URL → exits 1 and prints "NEON_DB_URL not set"
  - Script runs the expected SQL queries when DB is available (fake cursor)
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = str(Path(__file__).parent.parent / "scripts" / "check_neon_budget.py")
REPO_ROOT = str(Path(__file__).parent.parent)


def _run_script(tmp_path: Path, env_overrides: dict) -> subprocess.CompletedProcess:
    """Run check_neon_budget.py as a subprocess with a fake psycopg2."""
    env = {k: v for k, v in os.environ.items() if k not in ("NEON_DB_URL",)}
    env.update(env_overrides)
    # Prepend tmp_path so our fake psycopg2 package is found first
    pythonpath = f"{tmp_path}:{REPO_ROOT}"
    env["PYTHONPATH"] = pythonpath
    return subprocess.run(
        [sys.executable, SCRIPT],
        capture_output=True,
        text=True,
        env=env,
    )


def _make_fake_psycopg2(tmp_path: Path) -> None:
    """Write a minimal fake psycopg2 package into tmp_path."""
    pkg = tmp_path / "psycopg2"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        "def connect(url): return _FakeConn()\n"
        "class _FakeConn:\n"
        "    def __enter__(self): return self\n"
        "    def __exit__(self, *a): pass\n"
        "    def cursor(self, cursor_factory=None): return _FakeCursor()\n"
        "class _FakeCursor:\n"
        "    def execute(self, sql, params=None): pass\n"
        "    def fetchone(self): return None\n"
        "    def fetchall(self): return []\n"
        "    def __enter__(self): return self\n"
        "    def __exit__(self, *a): pass\n"
    )
    (pkg / "extras.py").write_text("class RealDictCursor: pass\n")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMissingNeonUrl:
    def test_exits_1_when_neon_url_absent(self, tmp_path):
        _make_fake_psycopg2(tmp_path)
        result = _run_script(tmp_path, {})
        assert result.returncode == 1

    def test_prints_neon_url_not_set(self, tmp_path):
        _make_fake_psycopg2(tmp_path)
        result = _run_script(tmp_path, {})
        assert "NEON_DB_URL not set" in result.stdout


class TestWithFakeDb:
    def test_exits_0_when_neon_url_set(self, tmp_path):
        _make_fake_psycopg2(tmp_path)
        result = _run_script(tmp_path, {"NEON_DB_URL": "postgresql://fake/db"})
        assert result.returncode == 0

    def test_prints_checking_budget(self, tmp_path):
        _make_fake_psycopg2(tmp_path)
        result = _run_script(tmp_path, {"NEON_DB_URL": "postgresql://fake/db"})
        assert "Checking budget" in result.stdout

    def test_no_budget_found_when_fetchone_returns_none(self, tmp_path):
        _make_fake_psycopg2(tmp_path)
        result = _run_script(tmp_path, {"NEON_DB_URL": "postgresql://fake/db"})
        assert "No budget found" in result.stdout

    def test_respects_default_user_id(self, tmp_path):
        _make_fake_psycopg2(tmp_path)
        result = _run_script(
            tmp_path,
            {"NEON_DB_URL": "postgresql://fake/db", "DEFAULT_USER_ID": "testuser"},
        )
        assert "testuser" in result.stdout
