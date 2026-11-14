"""The test session never reads a .env file or inherits live credentials.

Modules such as beeminder_client and twilio_sender call a bare load_dotenv()
at import. That walks up from the module's directory, so a worktree under
the user's checkout found the checkout's real .env: the suite then ran DDL
against live Neon and opened HTTPS connections to Beeminder. tests/conftest.py
neutralises dotenv and strips live-service keys before any project import,
unless MECRIS_TESTS_USE_ENV=1 opts back in.

Assertion messages name keys only, never values.
"""
import importlib.util
import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("MECRIS_TESTS_USE_ENV") == "1",
    reason="MECRIS_TESTS_USE_ENV=1 opts the session back into .env and live keys",
)

LIVE_KEYS = ("NEON_DB_URL", "DATABASE_URL", "CLAUDE_API_KEY")
LIVE_PREFIXES = ("TWILIO_", "BEEMINDER_", "ANTHROPIC_", "OPENROUTER_", "GROQ_")
SENTINEL = "MECRIS_DOTENV_ISOLATION_SENTINEL"


def test_no_live_service_keys_in_the_session_environment():
    leaked = sorted(
        k for k in os.environ if k in LIVE_KEYS or k.startswith(LIVE_PREFIXES)
    )
    assert leaked == []


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
    leaked = sorted(
        k for k in os.environ if k in LIVE_KEYS or k.startswith(LIVE_PREFIXES)
    )
    assert leaked == []
