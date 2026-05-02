"""
Unit tests for scripts/migrate_pii_encryption.py migrate() function.

All psycopg2 I/O is mocked. No DB, network, or filesystem access required.
Groups:
  - TestMigrateEarlyReturn (2): missing NEON_DB_URL / MASTER_ENCRYPTION_KEY returns False
  - TestMigrateColumns (2): adds missing user/log columns / skips present ones
  - TestMigrateBeeminderData (2): encrypts plaintext beeminder_user / skips empty rows
  - TestMigrateEnvCreds (2): migrates env token for DEFAULT_USER_ID / skips if absent
  - TestMigrateFailure (1): DB exception returns False

Total: 9 tests
"""

import sys
import os
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Bootstrap: mock psycopg2 and dotenv before importing the module
# ---------------------------------------------------------------------------

_mock_psycopg2 = MagicMock()
sys.modules.setdefault("psycopg2", _mock_psycopg2)
sys.modules.setdefault("dotenv", MagicMock())

from scripts.migrate_pii_encryption import migrate  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_cursor(user_columns=None, log_columns=None, beeminder_rows=None, env_cred_row=None):
    """Return a cursor whose fetchall/fetchone side_effects match the migration query order.

    Query sequence in migrate():
      1. SELECT column_name ... WHERE table_name = 'users'       → fetchall
      2. SELECT column_name ... WHERE table_name = 'message_log' → fetchall
      3. SELECT pocket_id_sub, beeminder_user ... WHERE ...      → fetchall
      4. (optional) SELECT beeminder_token_encrypted, ...        → fetchone
    """
    if user_columns is None:
        user_columns = []
    if log_columns is None:
        log_columns = []
    if beeminder_rows is None:
        beeminder_rows = []

    cur = MagicMock()
    cur.fetchall.side_effect = [
        [(col,) for col in user_columns],  # query 1: users column names
        [(col,) for col in log_columns],   # query 2: message_log column names
        beeminder_rows,                    # query 3: beeminder_user rows to migrate
    ]
    cur.fetchone.return_value = env_cred_row

    cur.__enter__ = lambda s: s
    cur.__exit__ = MagicMock(return_value=False)
    return cur


def _make_mock_conn(cursor):
    conn = MagicMock()
    conn.cursor.return_value = cursor
    conn.__enter__ = lambda s: s
    conn.__exit__ = MagicMock(return_value=False)
    return conn


_BASE_ENV = {
    "NEON_DB_URL": "postgresql://fake",
    "MASTER_ENCRYPTION_KEY": "test-key-32-chars-xxxxxxxxxxxxxxx",
}


# ---------------------------------------------------------------------------
# TestMigrateEarlyReturn
# ---------------------------------------------------------------------------

class TestMigrateEarlyReturn:
    def test_no_neon_db_url_returns_false(self):
        """migrate() returns False immediately when NEON_DB_URL is absent."""
        env = {"MASTER_ENCRYPTION_KEY": "test-key"}
        with patch.dict(os.environ, env, clear=True):
            os.environ.pop("NEON_DB_URL", None)
            with patch.object(sys.modules["psycopg2"], "connect") as mock_connect:
                result = migrate()
        assert result is False
        mock_connect.assert_not_called()

    def test_no_master_key_returns_false(self):
        """migrate() returns False immediately when MASTER_ENCRYPTION_KEY is absent."""
        env = {"NEON_DB_URL": "postgresql://fake"}
        with patch.dict(os.environ, env, clear=True):
            os.environ.pop("MASTER_ENCRYPTION_KEY", None)
            with patch.object(sys.modules["psycopg2"], "connect") as mock_connect:
                result = migrate()
        assert result is False
        mock_connect.assert_not_called()


# ---------------------------------------------------------------------------
# TestMigrateColumns
# ---------------------------------------------------------------------------

class TestMigrateColumns:
    def test_missing_columns_issue_alter_table(self):
        """When required columns are absent, ALTER TABLE is issued for each missing one."""
        cur = _make_mock_cursor(user_columns=[], log_columns=[])
        conn = _make_mock_conn(cur)
        mock_enc = MagicMock()
        mock_enc_cls = MagicMock(return_value=mock_enc)

        with patch.dict(os.environ, _BASE_ENV, clear=True):
            os.environ.pop("DEFAULT_USER_ID", None)
            with patch.object(sys.modules["psycopg2"], "connect", return_value=conn):
                with patch("scripts.migrate_pii_encryption.EncryptionService", mock_enc_cls):
                    result = migrate()

        executed_sql = [str(c.args[0]).strip() for c in cur.execute.call_args_list]
        alter_stmts = [sql for sql in executed_sql if "ALTER TABLE" in sql]
        # 4 user cols + 3 message_log cols = 7 ALTER statements
        assert len(alter_stmts) == 7
        assert result is True
        conn.commit.assert_called_once()

    def test_present_columns_skip_alter_table(self):
        """When all required columns already exist, no ALTER TABLE is issued."""
        present_user_cols = [
            "beeminder_user_encrypted",
            "phone_number_encrypted",
            "clozemaster_email_encrypted",
            "clozemaster_password_encrypted",
        ]
        present_log_cols = ["status", "error_msg", "content"]
        cur = _make_mock_cursor(user_columns=present_user_cols, log_columns=present_log_cols)
        conn = _make_mock_conn(cur)
        mock_enc = MagicMock()
        mock_enc_cls = MagicMock(return_value=mock_enc)

        with patch.dict(os.environ, _BASE_ENV, clear=True):
            os.environ.pop("DEFAULT_USER_ID", None)
            with patch.object(sys.modules["psycopg2"], "connect", return_value=conn):
                with patch("scripts.migrate_pii_encryption.EncryptionService", mock_enc_cls):
                    result = migrate()

        executed_sql = [str(c.args[0]).strip() for c in cur.execute.call_args_list]
        alter_stmts = [sql for sql in executed_sql if "ALTER TABLE" in sql]
        assert len(alter_stmts) == 0
        assert result is True
        conn.commit.assert_called_once()


# ---------------------------------------------------------------------------
# TestMigrateBeeminderData
# ---------------------------------------------------------------------------

class TestMigrateBeeminderData:
    def test_beeminder_user_row_is_encrypted_and_updated(self):
        """Plaintext beeminder_user rows are encrypted and written back to DB."""
        beeminder_rows = [("user-001", "my_beeminder_name")]
        cur = _make_mock_cursor(beeminder_rows=beeminder_rows)
        conn = _make_mock_conn(cur)
        mock_enc = MagicMock()
        mock_enc.encrypt.return_value = "enc-value"
        mock_enc_cls = MagicMock(return_value=mock_enc)

        with patch.dict(os.environ, _BASE_ENV, clear=True):
            os.environ.pop("DEFAULT_USER_ID", None)
            with patch.object(sys.modules["psycopg2"], "connect", return_value=conn):
                with patch("scripts.migrate_pii_encryption.EncryptionService", mock_enc_cls):
                    result = migrate()

        mock_enc.encrypt.assert_called_once_with("my_beeminder_name")
        update_calls = [
            c for c in cur.execute.call_args_list
            if "UPDATE users SET beeminder_user_encrypted" in str(c.args[0])
        ]
        assert len(update_calls) == 1
        params = update_calls[0].args[1]
        assert params[0] == "enc-value"
        assert params[1] == "user-001"
        assert result is True

    def test_empty_beeminder_rows_skips_encrypt_and_update(self):
        """When no beeminder_user rows need migration, encrypt is not called."""
        cur = _make_mock_cursor(beeminder_rows=[])
        conn = _make_mock_conn(cur)
        mock_enc = MagicMock()
        mock_enc_cls = MagicMock(return_value=mock_enc)

        with patch.dict(os.environ, _BASE_ENV, clear=True):
            os.environ.pop("DEFAULT_USER_ID", None)
            with patch.object(sys.modules["psycopg2"], "connect", return_value=conn):
                with patch("scripts.migrate_pii_encryption.EncryptionService", mock_enc_cls):
                    result = migrate()

        mock_enc.encrypt.assert_not_called()
        assert result is True


# ---------------------------------------------------------------------------
# TestMigrateEnvCreds
# ---------------------------------------------------------------------------

class TestMigrateEnvCreds:
    def test_env_token_migrated_when_db_row_is_empty(self):
        """When DEFAULT_USER_ID is set and DB has no token, env token is encrypted and written."""
        # env_cred_row tuple: (beeminder_token_encrypted, clozemaster_email_encrypted)
        cur = _make_mock_cursor(env_cred_row=(None, None))
        conn = _make_mock_conn(cur)
        mock_enc = MagicMock()
        mock_enc.encrypt.return_value = "enc-tok"
        mock_enc_cls = MagicMock(return_value=mock_enc)

        env = {**_BASE_ENV, "DEFAULT_USER_ID": "uid-999", "BEEMINDER_AUTH_TOKEN": "my-token"}
        with patch.dict(os.environ, env, clear=True):
            with patch.object(sys.modules["psycopg2"], "connect", return_value=conn):
                with patch("scripts.migrate_pii_encryption.EncryptionService", mock_enc_cls):
                    result = migrate()

        # An UPDATE for uid-999 should have been issued
        update_calls = [
            c for c in cur.execute.call_args_list
            if "UPDATE users SET" in str(c.args[0])
            and c.args[1] is not None
            and "uid-999" in str(c.args[1])
        ]
        assert len(update_calls) == 1
        assert result is True

    def test_no_default_user_id_skips_env_migration(self):
        """When DEFAULT_USER_ID is absent, the env credential migration block is skipped."""
        cur = _make_mock_cursor()
        conn = _make_mock_conn(cur)
        mock_enc = MagicMock()
        mock_enc_cls = MagicMock(return_value=mock_enc)

        env = {**_BASE_ENV, "BEEMINDER_AUTH_TOKEN": "tok"}
        with patch.dict(os.environ, env, clear=True):
            os.environ.pop("DEFAULT_USER_ID", None)
            with patch.object(sys.modules["psycopg2"], "connect", return_value=conn):
                with patch("scripts.migrate_pii_encryption.EncryptionService", mock_enc_cls):
                    result = migrate()

        # fetchone is only called inside the DEFAULT_USER_ID branch
        assert cur.fetchone.call_count == 0
        assert result is True


# ---------------------------------------------------------------------------
# TestMigrateFailure
# ---------------------------------------------------------------------------

class TestMigrateFailure:
    def test_db_exception_returns_false(self):
        """When psycopg2.connect raises, migrate() catches the exception and returns False."""
        mock_enc_cls = MagicMock()

        with patch.dict(os.environ, _BASE_ENV, clear=True):
            with patch.object(sys.modules["psycopg2"], "connect", side_effect=Exception("DB down")):
                with patch("scripts.migrate_pii_encryption.EncryptionService", mock_enc_cls):
                    result = migrate()

        assert result is False
