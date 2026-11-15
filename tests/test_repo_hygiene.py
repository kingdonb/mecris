"""Repo hygiene guard (#348).

The repo root is for live entry points, not one-off scripts, screenshots or
tests that CI never collects. Some of those root tests acted at import time
(one sent a real WhatsApp message), and pyproject.toml's testpaths would
collect them if pytest.ini ever went away. Build output and local databases
do not belong in git either.

Retired files live under attic/ (moved with git mv, so history follows them).
"""
import fnmatch
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _git(*args):
    if shutil.which("git") is None:
        pytest.skip("git is not available")
    result = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True)
    if result.returncode != 0 and b"not a git repository" in result.stderr:
        pytest.skip("not running inside a git checkout")
    return result


def _tracked():
    out = _git("ls-files", "-z").stdout.decode("utf-8", "surrogateescape")
    return [p for p in out.split("\0") if p]


def _root_files():
    return [p for p in _tracked() if "/" not in p]


def test_no_test_modules_at_repo_root():
    offenders = [p for p in _root_files() if fnmatch.fnmatch(p, "test_*.py") or fnmatch.fnmatch(p, "test_*.sh")]
    assert offenders == [], "root tests are never collected by CI; move them under tests/ or attic/tests/"


def test_no_one_off_scripts_at_repo_root():
    patterns = ["fix_*.py", "check_*.py", "simple_main.py", "*-spintainer.yaml"]
    offenders = [p for p in _root_files() if any(fnmatch.fnmatch(p, pat) for pat in patterns)]
    assert offenders == []


def test_no_one_off_rewrite_scripts_in_scripts_dir():
    offenders = [
        p for p in _tracked()
        if p.startswith("scripts/") and p.count("/") == 1
        and (fnmatch.fnmatch(p, "scripts/fix_*.py") or fnmatch.fnmatch(p, "scripts/refactor_*.py"))
    ]
    assert offenders == []


def test_no_images_or_documents_at_repo_root():
    exts = (".png", ".jpg", ".jpeg", ".gif", ".pdf")
    offenders = [p for p in _root_files() if p.lower().endswith(exts)]
    assert offenders == []


def test_no_stray_data_files_at_repo_root():
    patterns = ["*.db", "claude_usage.json", "issue_summary.txt", "coverage_baseline.txt", "mecris_test_report_*.json"]
    offenders = [p for p in _root_files() if any(fnmatch.fnmatch(p, pat) for pat in patterns)]
    assert offenders == []


def test_no_tracked_build_output():
    offenders = [p for p in _tracked() if p.startswith("target/") or "/target/" in p]
    assert len(offenders) == 0, f"{len(offenders)} tracked files under a target/ directory"


def test_no_tracked_sqlite_outside_attic():
    offenders = [p for p in _tracked() if p.endswith(".db") and not p.startswith("attic/")]
    assert offenders == []


@pytest.mark.parametrize("path", [
    "claude_usage.json",
    "mecris_usage.db",
    "some/where/local.db",
    "poc/v6-hello/target/debug/build.rs",
    "some-new-crate/target/release/deps/some_new_crate.d",
])
def test_gitignore_covers_generated_artifacts(path):
    result = _git("check-ignore", "-q", "--no-index", path)
    assert result.returncode == 0, f"{path} should be ignored by .gitignore"
