"""Unit tests for services/credentials_manager.py — CredentialsManager class.

Covers:
- _is_uuid: UUID detection (true/false cases)
- resolve_familiar_id: DB lookup (no URL, found, not found, exception)
- resolve_user_id: all resolution branches (provided, file, env, standalone, cloud, familiar)

Closes yebyen/mecris#183
"""
import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


def _make_cm(tmp_path):
    """Instantiate CredentialsManager with config_dir under tmp_path."""
    sys.modules.pop("services.credentials_manager", None)
    from services.credentials_manager import CredentialsManager
    cm = CredentialsManager()
    cm.config_dir = tmp_path / ".mecris"
    cm.credentials_file = tmp_path / ".mecris" / "credentials.json"
    return cm


# ---------------------------------------------------------------------------
# _is_uuid
# ---------------------------------------------------------------------------

class TestIsUuid:
    def setup_method(self):
        sys.modules.pop("services.credentials_manager", None)
        from services.credentials_manager import CredentialsManager
        self.cm = CredentialsManager()

    def test_standard_uuid_with_hyphens(self):
        assert self.cm._is_uuid("550e8400-e29b-41d4-a716-446655440000") is True

    def test_hex_string_32_chars_no_hyphens(self):
        assert self.cm._is_uuid("550e8400e29b41d4a716446655440000") is True

    def test_familiar_name_short_returns_false(self):
        assert self.cm._is_uuid("yebyen") is False

    def test_none_returns_false(self):
        assert self.cm._is_uuid(None) is False

    def test_empty_string_returns_false(self):
        assert self.cm._is_uuid("") is False

    def test_local_prefix_returns_false(self):
        # "local-abc12345" is 14 chars, less than 32
        assert self.cm._is_uuid("local-abc12345") is False


# ---------------------------------------------------------------------------
# resolve_familiar_id
# ---------------------------------------------------------------------------

class TestResolveFamiliarId:
    def setup_method(self, tmp_path=None):
        sys.modules.pop("services.credentials_manager", None)
        from services.credentials_manager import CredentialsManager
        self.cm = CredentialsManager()

    def test_no_neon_db_url_returns_none(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NEON_DB_URL", None)
            result = self.cm.resolve_familiar_id("yebyen")
        assert result is None

    def test_found_in_db_returns_pocket_id_sub(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = ("some-uuid-sub-here",)

        with patch.dict(os.environ, {"NEON_DB_URL": "postgres://fake"}):
            with patch("psycopg2.connect", return_value=mock_conn):
                result = self.cm.resolve_familiar_id("yebyen")

        assert result == "some-uuid-sub-here"

    def test_not_found_in_db_returns_none(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None

        with patch.dict(os.environ, {"NEON_DB_URL": "postgres://fake"}):
            with patch("psycopg2.connect", return_value=mock_conn):
                result = self.cm.resolve_familiar_id("unknown-user")

        assert result is None

    def test_db_exception_returns_none(self):
        with patch.dict(os.environ, {"NEON_DB_URL": "postgres://fake"}):
            with patch("psycopg2.connect", side_effect=Exception("connection refused")):
                result = self.cm.resolve_familiar_id("yebyen")

        assert result is None


# ---------------------------------------------------------------------------
# resolve_user_id
# ---------------------------------------------------------------------------

class TestResolveUserId:
    def test_provided_uuid_returned_directly(self, tmp_path):
        cm = _make_cm(tmp_path)
        uuid_id = "550e8400-e29b-41d4-a716-446655440000"
        with patch.dict(os.environ, {"MECRIS_MODE": "standalone"}, clear=False):
            result = cm.resolve_user_id(uuid_id)
        assert result == uuid_id

    def test_provided_local_id_returned_directly(self, tmp_path):
        cm = _make_cm(tmp_path)
        local_id = "local-abc12345"
        with patch.dict(os.environ, {"MECRIS_MODE": "standalone"}, clear=False):
            result = cm.resolve_user_id(local_id)
        assert result == local_id

    def test_reads_user_id_from_credentials_file(self, tmp_path):
        cm = _make_cm(tmp_path)
        cm.config_dir.mkdir(parents=True)
        cm.credentials_file.write_text(json.dumps({"user_id": "file-user-id"}))
        with patch.dict(os.environ, {"MECRIS_MODE": "standalone"}, clear=False):
            os.environ.pop("DEFAULT_USER_ID", None)
            result = cm.resolve_user_id()
        assert result == "file-user-id"

    def test_falls_back_to_default_user_id_env(self, tmp_path):
        cm = _make_cm(tmp_path)
        # No credentials file exists
        with patch.dict(os.environ, {"DEFAULT_USER_ID": "env-user-id", "MECRIS_MODE": "standalone"}):
            result = cm.resolve_user_id()
        assert result == "env-user-id"

    def test_standalone_mode_no_id_returns_none(self, tmp_path):
        cm = _make_cm(tmp_path)
        env = {"MECRIS_MODE": "standalone"}
        # Remove DEFAULT_USER_ID if present
        env_no_default = {k: v for k, v in os.environ.items() if k != "DEFAULT_USER_ID"}
        env_no_default["MECRIS_MODE"] = "standalone"
        with patch.dict(os.environ, env_no_default, clear=True):
            result = cm.resolve_user_id()
        assert result is None

    def test_cloud_mode_no_id_returns_none(self, tmp_path):
        cm = _make_cm(tmp_path)
        env = {k: v for k, v in os.environ.items() if k not in ("DEFAULT_USER_ID", "MECRIS_MODE")}
        env["MECRIS_MODE"] = "cloud"
        with patch.dict(os.environ, env, clear=True):
            result = cm.resolve_user_id()
        assert result is None

    def test_familiar_name_resolves_via_db(self, tmp_path):
        cm = _make_cm(tmp_path)
        resolved_uuid = "550e8400-e29b-41d4-a716-446655440000"

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = (resolved_uuid,)

        with patch.dict(os.environ, {"NEON_DB_URL": "postgres://fake", "MECRIS_MODE": "standalone"}):
            with patch("psycopg2.connect", return_value=mock_conn):
                result = cm.resolve_user_id("yebyen")

        assert result == resolved_uuid

    def test_familiar_name_not_in_db_returns_familiar_name(self, tmp_path):
        """If familiar_id lookup returns None, resolve_user_id falls through to return the original ID."""
        cm = _make_cm(tmp_path)

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None

        with patch.dict(os.environ, {"NEON_DB_URL": "postgres://fake", "MECRIS_MODE": "standalone"}):
            with patch("psycopg2.connect", return_value=mock_conn):
                result = cm.resolve_user_id("unknown-familiar")

        # Falls through — returns the original target_id
        assert result == "unknown-familiar"
