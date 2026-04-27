"""
Tests for services.secret_manager.SecretManager and the env-isolation
changes in ghost.headless_loopback.HeadlessLoopback.

Covers the three validation criteria from yebyen/mecris#286:
  1. SecretManager.get_secrets returns only the requested keys.
  2. HeadlessLoopback.run() passes a minimal env dict to subprocess.Popen.
  3. The parent os.environ is not modified after a run.

Also covers the Neon fallback criteria from yebyen/mecris#288:
  4. Key absent from env but present in Neon → returned in result.
  5. Key absent from both env and Neon → omitted.
  6. NEON_DB_URL unset → Neon lookup skipped entirely.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from ghost.headless_loopback import HeadlessLoopback
from services.secret_manager import HEADLESS_LOOPBACK_KEYS, SecretManager


# ---------------------------------------------------------------------------
# 1. SecretManager.get_secrets — returns only requested keys
# ---------------------------------------------------------------------------


class TestSecretManagerGetSecrets:
    """SecretManager.get_secrets fetches only the keys it is asked for."""

    def test_returns_only_requested_keys(self):
        """get_secrets with a single key returns exactly that key."""
        sm = SecretManager()
        fake_env = {"GEMINI_API_KEY": "tok_abc", "NEON_DB_URL": "postgres://secret"}
        with patch.dict(os.environ, fake_env, clear=True):
            result = sm.get_secrets(["GEMINI_API_KEY"])
        assert result == {"GEMINI_API_KEY": "tok_abc"}
        assert "NEON_DB_URL" not in result

    def test_returns_multiple_requested_keys(self):
        """get_secrets with multiple keys returns all that are present."""
        sm = SecretManager()
        fake_env = {"KEY_A": "val_a", "KEY_B": "val_b", "KEY_C": "val_c"}
        with patch.dict(os.environ, fake_env, clear=True):
            result = sm.get_secrets(["KEY_A", "KEY_B"])
        assert result == {"KEY_A": "val_a", "KEY_B": "val_b"}
        assert "KEY_C" not in result

    def test_missing_key_omitted_not_none(self):
        """A key absent from the environment is not present in the result (not set to None)."""
        sm = SecretManager()
        with patch.dict(os.environ, {}, clear=True):
            result = sm.get_secrets(["MISSING_KEY"])
        assert "MISSING_KEY" not in result

    def test_empty_keys_list_returns_empty_dict(self):
        sm = SecretManager()
        with patch.dict(os.environ, {"SOME_KEY": "val"}, clear=True):
            result = sm.get_secrets([])
        assert result == {}

    def test_returned_dict_is_independent_copy(self):
        """Modifying the returned dict must not alter os.environ."""
        sm = SecretManager()
        with patch.dict(os.environ, {"GEMINI_API_KEY": "original"}):
            result = sm.get_secrets(["GEMINI_API_KEY"])
            result["GEMINI_API_KEY"] = "tampered"
            assert os.environ.get("GEMINI_API_KEY") == "original"

    def test_partial_keys_present(self):
        """If only some requested keys exist, only those are returned."""
        sm = SecretManager()
        fake_env = {"KEY_PRESENT": "yes"}
        with patch.dict(os.environ, fake_env, clear=True):
            result = sm.get_secrets(["KEY_PRESENT", "KEY_ABSENT"])
        assert result == {"KEY_PRESENT": "yes"}

    def test_headless_loopback_keys_constant_is_non_empty(self):
        """HEADLESS_LOOPBACK_KEYS must name at least one key."""
        assert len(HEADLESS_LOOPBACK_KEYS) >= 1

    def test_gemini_api_key_in_headless_loopback_keys(self):
        assert "GEMINI_API_KEY" in HEADLESS_LOOPBACK_KEYS


# ---------------------------------------------------------------------------
# 2. HeadlessLoopback passes a minimal env to subprocess.Popen
# ---------------------------------------------------------------------------


def _make_proc(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    proc = MagicMock()
    proc.returncode = returncode
    proc.pid = 12345
    proc.communicate.return_value = (stdout, stderr)
    return proc


class TestHeadlessLoopbackEnvIsolation:
    """HeadlessLoopback.run() passes only minimal env to Popen."""

    def _sm_with(self, secrets: dict) -> SecretManager:
        """Return a SecretManager that always yields *secrets* regardless of keys."""
        sm = MagicMock(spec=SecretManager)
        sm.get_secrets.return_value = secrets
        return sm

    def test_popen_called_with_env_kwarg(self):
        """Popen must be called with an explicit env= argument."""
        proc = _make_proc()
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc) as mock_popen:
            HeadlessLoopback(secret_manager=self._sm_with({})).run("prompt")
        call_kwargs = mock_popen.call_args.kwargs
        assert "env" in call_kwargs, "Popen must receive an explicit env= kwarg"

    def test_popen_env_contains_secret_key(self):
        """The env passed to Popen includes the secret key from SecretManager."""
        proc = _make_proc()
        secrets = {"GEMINI_API_KEY": "tok_xyz"}
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc) as mock_popen:
            HeadlessLoopback(secret_manager=self._sm_with(secrets)).run("prompt")
        env = mock_popen.call_args.kwargs["env"]
        assert env.get("GEMINI_API_KEY") == "tok_xyz"

    def test_popen_env_excludes_unrequested_secrets(self):
        """The env passed to Popen must NOT contain NEON_DB_URL or other credentials."""
        proc = _make_proc()
        # Inject a sensitive var into os.environ that HeadlessLoopback must NOT forward
        with patch.dict(os.environ, {"NEON_DB_URL": "postgres://secret"}):
            with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc) as mock_popen:
                # SecretManager only returns GEMINI_API_KEY — NEON_DB_URL not requested
                HeadlessLoopback(secret_manager=self._sm_with({"GEMINI_API_KEY": "tok"})).run("p")
        env = mock_popen.call_args.kwargs["env"]
        assert "NEON_DB_URL" not in env

    def test_popen_env_contains_path(self):
        """The env passed to Popen includes PATH so the subprocess can locate executables."""
        proc = _make_proc()
        with patch.dict(os.environ, {"PATH": "/usr/bin:/bin"}):
            with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc) as mock_popen:
                HeadlessLoopback(secret_manager=self._sm_with({})).run("prompt")
        env = mock_popen.call_args.kwargs["env"]
        assert "PATH" in env

    def test_popen_env_is_minimal_no_full_parent_env(self):
        """The env dict must be smaller than the full os.environ."""
        proc = _make_proc()
        # Pollute os.environ with a known key that should NOT appear
        with patch.dict(os.environ, {"MECRIS_SHOULD_NOT_LEAK": "secret_value"}):
            with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc) as mock_popen:
                HeadlessLoopback(secret_manager=self._sm_with({})).run("prompt")
        env = mock_popen.call_args.kwargs["env"]
        assert "MECRIS_SHOULD_NOT_LEAK" not in env


# ---------------------------------------------------------------------------
# 4. SecretManager Neon fallback (yebyen/mecris#288)
# ---------------------------------------------------------------------------


class TestSecretManagerNeonFallback:
    """SecretManager.get_secrets falls back to Neon secure_variables when NEON_DB_URL is set."""

    def _make_neon_connect(self, key_to_value: dict):
        """Return a callable that simulates psycopg2.connect returning rows from key_to_value."""

        def connect(url):
            cur = MagicMock()
            cur.__enter__.return_value = cur
            cur._last_key = None

            def execute(sql, params):
                cur._last_key = params[0]

            def fetchone():
                val = key_to_value.get(cur._last_key)
                return (val,) if val is not None else None

            cur.execute = execute
            cur.fetchone = fetchone

            conn = MagicMock()
            conn.__enter__.return_value = conn
            conn.cursor.return_value = cur
            return conn

        return connect

    def test_key_from_neon_when_absent_from_env(self):
        """A key absent from env but present in Neon secure_variables is returned."""
        connect = self._make_neon_connect({"GEMINI_API_KEY": "neon_tok"})
        sm = SecretManager(_neon_connect=connect)
        with patch.dict(os.environ, {"NEON_DB_URL": "postgres://test"}, clear=True):
            result = sm.get_secrets(["GEMINI_API_KEY"])
        assert result == {"GEMINI_API_KEY": "neon_tok"}

    def test_key_absent_from_both_env_and_neon(self):
        """A key absent from both env and Neon is omitted from the result."""
        connect = self._make_neon_connect({})  # no keys in Neon
        sm = SecretManager(_neon_connect=connect)
        with patch.dict(os.environ, {"NEON_DB_URL": "postgres://test"}, clear=True):
            result = sm.get_secrets(["MISSING_KEY"])
        assert "MISSING_KEY" not in result

    def test_neon_skipped_when_neon_db_url_unset(self):
        """When NEON_DB_URL is absent, Neon is never queried."""
        connect = MagicMock()
        sm = SecretManager(_neon_connect=connect)
        with patch.dict(os.environ, {}, clear=True):
            result = sm.get_secrets(["SOME_KEY"])
        connect.assert_not_called()
        assert "SOME_KEY" not in result

    def test_env_key_takes_precedence_and_neon_not_queried(self):
        """When all requested keys are in env, Neon connect is never called."""
        connect = MagicMock()
        sm = SecretManager(_neon_connect=connect)
        with patch.dict(
            os.environ,
            {"NEON_DB_URL": "postgres://test", "MY_KEY": "env_val"},
            clear=True,
        ):
            result = sm.get_secrets(["MY_KEY"])
        connect.assert_not_called()
        assert result == {"MY_KEY": "env_val"}

    def test_neon_error_is_silent_key_omitted(self):
        """If Neon raises, the key is silently omitted (fail-safe)."""

        def bad_connect(url):
            raise RuntimeError("connection refused")

        sm = SecretManager(_neon_connect=bad_connect)
        with patch.dict(os.environ, {"NEON_DB_URL": "postgres://test"}, clear=True):
            result = sm.get_secrets(["FRAGILE_KEY"])
        assert "FRAGILE_KEY" not in result


# ---------------------------------------------------------------------------
# 3. Parent os.environ not modified after a run
# ---------------------------------------------------------------------------


class TestParentEnvUnmodified:
    """HeadlessLoopback.run() must leave os.environ exactly as it found it."""

    def test_os_environ_unchanged_after_successful_run(self):
        proc = _make_proc()
        snapshot_before = dict(os.environ)
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc):
            HeadlessLoopback().run("prompt")
        assert dict(os.environ) == snapshot_before

    def test_os_environ_unchanged_after_spawn_error(self):
        snapshot_before = dict(os.environ)
        with patch("ghost.headless_loopback.subprocess.Popen", side_effect=FileNotFoundError):
            HeadlessLoopback().run("prompt")
        assert dict(os.environ) == snapshot_before

    def test_os_environ_unchanged_after_timeout(self):
        import subprocess as _sp

        proc = MagicMock()
        proc.pid = 99
        proc.returncode = -9
        proc.communicate.side_effect = [
            _sp.TimeoutExpired(cmd="gemini", timeout=1),
            ("", ""),
        ]
        snapshot_before = dict(os.environ)
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc), \
             patch("ghost.headless_loopback.os.killpg"), \
             patch("ghost.headless_loopback.os.getpgid", return_value=99):
            HeadlessLoopback(timeout=1).run("prompt")
        assert dict(os.environ) == snapshot_before
