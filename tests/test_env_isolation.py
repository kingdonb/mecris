"""The test session never reads a .env file or inherits live credentials.

Modules such as beeminder_client and twilio_sender call a bare load_dotenv()
at import. That walks up from the module's directory, so a worktree under
the user's checkout found the checkout's real .env: the suite then ran DDL
against live Neon and opened HTTPS connections to Beeminder. tests/conftest.py
neutralises dotenv and strips live-service keys before any project import,
unless MECRIS_TESTS_USE_ENV=1 opts back in. The one exception is a database
URL on a loopback host: CI points NEON_DB_URL at its own Postgres service on
localhost, and the Postgres-backed tests need it.

Assertion messages name keys only, never values.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("MECRIS_TESTS_USE_ENV") == "1",
    reason="MECRIS_TESTS_USE_ENV=1 opts the session back into .env and live keys",
)

LIVE_KEYS = ("NEON_DB_URL", "DATABASE_URL", "CLAUDE_API_KEY")
LIVE_PREFIXES = ("TWILIO_", "BEEMINDER_", "ANTHROPIC_", "OPENROUTER_", "GROQ_")
DB_KEYS = ("NEON_DB_URL", "DATABASE_URL")
SENTINEL = "MECRIS_DOTENV_ISOLATION_SENTINEL"

REPO_TESTS = Path(__file__).resolve().parent


def _loopback_url(value):
    # Deliberately independent of the conftest's own check: a database URL
    # may stay only if it is a postgres URL on a loopback host and carries no
    # query string that could redirect libpq elsewhere.
    parsed = urlsplit(value)
    return (
        parsed.scheme in ("postgres", "postgresql")
        and parsed.hostname in ("localhost", "127.0.0.1", "::1")
        and not parsed.query
    )


def _leaked_keys():
    return sorted(
        k
        for k in os.environ
        if (k in LIVE_KEYS or k.startswith(LIVE_PREFIXES))
        and not (k in DB_KEYS and _loopback_url(os.environ[k]))
    )


def test_no_live_service_keys_in_the_session_environment():
    # A loopback NEON_DB_URL / DATABASE_URL (CI's Postgres service) may stay;
    # every other live key, and every non-local database URL, must be gone.
    assert _leaked_keys() == []


def _run_conftest_probe(tmp_path, extra_env):
    """Run a one-test pytest session under a copy of tests/conftest.py.

    The probe test writes which database keys survived the conftest into a
    file, so the parent never sees or prints the values themselves.
    """
    for name in ("conftest.py", "live_env_guard.py"):
        src = REPO_TESTS / name
        if src.exists():
            shutil.copy(src, tmp_path / name)
    report = tmp_path / "survivors.json"
    (tmp_path / "test_probe.py").write_text(
        "import json, os\n"
        "def test_probe():\n"
        f"    keys = {list(DB_KEYS) + ['TWILIO_PROBE', 'BEEMINDER_PROBE']!r}\n"
        f"    survivors = {{k: os.environ.get(k) for k in keys if k in os.environ}}\n"
        f"    open({str(report)!r}, 'w').write(json.dumps(survivors))\n"
    )
    env = {
        k: v
        for k, v in os.environ.items()
        if not (k in LIVE_KEYS or k.startswith(LIVE_PREFIXES))
    }
    env.pop("MECRIS_TESTS_USE_ENV", None)
    # The conftest's autouse fixture imports usage_tracker from the repo root.
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (str(REPO_TESTS.parent), env.get("PYTHONPATH", "")) if p
    )
    env.update(extra_env)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
         "--rootdir", str(tmp_path), str(tmp_path / "test_probe.py")],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    return json.loads(report.read_text())


LOCAL_URLS = [
    "postgresql://mecris:mecris@localhost:5432/mecrisdb",
    "postgresql://mecris:mecris@127.0.0.1:5432/mecrisdb",
    "postgres://mecris@[::1]:5432/mecrisdb",
    "postgresql://mecris@LOCALHOST/mecrisdb",
]

REMOTE_URLS = [
    "postgresql://u:p@db.example.invalid/neondb?sslmode=require",
    "postgresql://u:p@localhost.example.invalid/db",
    "postgresql://localhost:p@db.example.invalid/db",
    "postgresql://u@localhost,db.example.invalid/db",
    "postgresql://u@localhost/db?host=db.example.invalid",
    "postgresql://u@localhost/db?hostaddr=192.0.2.10",
    "postgresql://u@localhost/db?service=prod",
    "host=localhost dbname=mecrisdb",
    "mysql://u@localhost/db",
    "not a url",
    "",
]


@pytest.mark.parametrize("url", LOCAL_URLS)
def test_conftest_keeps_a_loopback_database_url(tmp_path, url):
    # CI runs the suite against a Postgres service on localhost; stripping
    # that URL silently skipped the Postgres-backed tests.
    survivors = _run_conftest_probe(
        tmp_path,
        {"NEON_DB_URL": url, "DATABASE_URL": url, "TWILIO_PROBE": "x", "BEEMINDER_PROBE": "x"},
    )
    assert survivors == {"NEON_DB_URL": url, "DATABASE_URL": url}


def test_conftest_strips_every_non_loopback_database_url(tmp_path):
    # One session per URL would be slow; NEON_DB_URL and DATABASE_URL are
    # checked independently, so pair them up and assert neither survives.
    for i in range(0, len(REMOTE_URLS), 2):
        pair = REMOTE_URLS[i:i + 2]
        neon, database = pair[0], pair[-1]
        run_dir = tmp_path / f"run{i}"
        run_dir.mkdir()
        survivors = _run_conftest_probe(
            run_dir, {"NEON_DB_URL": neon, "DATABASE_URL": database}
        )
        assert sorted(survivors) == [], f"remote URL kept for run {i}"


def test_conftest_keeps_a_local_url_and_strips_a_remote_one_side_by_side(tmp_path):
    survivors = _run_conftest_probe(
        tmp_path,
        {
            "NEON_DB_URL": "postgresql://mecris:mecris@localhost:5432/mecrisdb",
            "DATABASE_URL": "postgresql://u:p@db.example.invalid/neondb",
        },
    )
    assert sorted(survivors) == ["NEON_DB_URL"]


def test_a_bare_load_dotenv_does_not_read_an_ancestor_env_file(tmp_path, monkeypatch):
    # Reproduce the worktree layout: a .env in an ancestor directory and a
    # module below it that calls a bare load_dotenv() at import.
    monkeypatch.delenv(SENTINEL, raising=False)
    (tmp_path / ".env").write_text(f"{SENTINEL}=loaded\nNEON_DB_URL=postgres://from-dotenv\n")
    pkg = tmp_path / "worktrees" / "wt"
    pkg.mkdir(parents=True)
    module_file = pkg / "dotenv_probe_module.py"
    module_file.write_text("from dotenv import load_dotenv\nload_dotenv()\n")

    spec = importlib.util.spec_from_file_location("dotenv_probe_module", module_file)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        loaded = sorted(k for k in (SENTINEL, "NEON_DB_URL") if k in os.environ)
    finally:
        # Never leave the probe's values behind for later tests.
        os.environ.pop(SENTINEL, None)
        if os.environ.get("NEON_DB_URL") == "postgres://from-dotenv":
            os.environ.pop("NEON_DB_URL", None)
    assert loaded == []


def test_an_explicit_dotenv_path_is_not_read_either(tmp_path, monkeypatch):
    # mcp_server.py loads its own directory's .env by explicit path.
    monkeypatch.delenv(SENTINEL, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(f"{SENTINEL}=loaded\n")
    from dotenv import load_dotenv
    try:
        load_dotenv(dotenv_path=str(env_file))
        loaded = SENTINEL in os.environ
    finally:
        os.environ.pop(SENTINEL, None)
    assert loaded is False


def test_importing_modules_with_a_bare_load_dotenv_leaves_no_live_keys():
    # These modules call load_dotenv() at import; in a worktree that used to
    # pull the checkout's real .env into the session.
    import beeminder_client  # noqa: F401
    import twilio_sender  # noqa: F401
    assert _leaked_keys() == []
