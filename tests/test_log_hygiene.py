"""Log hygiene for the MCP server (#358 slice, #39 narrowed).

- mcp_server.py itself quiets httpx/httpcore and redacts auth_token values.
  Until now only an import side effect of scripts/clozemaster_scraper.py kept
  the Beeminder token (sent as ?auth_token=...) out of the log.
- MECRIS_LOG_FILE chooses the log path, and the test session points it at a
  temporary file, so pytest no longer writes into logs/mecris_server.log.
"""
import hashlib
import logging
import os
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest

REPO = Path(__file__).resolve().parents[1]
PROD_LOG = REPO / "logs" / "mecris_server.log"
SECRET = "sekr3tTokenValue"


def _digest(path: Path):
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fresh_import(extra_env=None, stub_scraper=True):
    """Import a fresh mcp_server, optionally without the real clozemaster scraper."""
    sys.modules.pop("mcp_server", None)
    env = {"NEON_DB_URL": "postgres://fake", "DEFAULT_USER_ID": "test-user"}
    env.update(extra_env or {})
    modules = {}
    if stub_scraper:
        fake = types.ModuleType("scripts.clozemaster_scraper")

        async def sync_clozemaster_to_beeminder(*args, **kwargs):
            return {}

        fake.sync_clozemaster_to_beeminder = sync_clozemaster_to_beeminder
        modules["scripts.clozemaster_scraper"] = fake
    with patch.dict(sys.modules, modules), patch.dict(os.environ, env), patch("psycopg2.connect"):
        import mcp_server
    return mcp_server


@pytest.fixture
def no_scraper_side_effect():
    """Undo any level an earlier import of the scraper left on httpx/httpcore."""
    saved = {name: logging.getLogger(name).level for name in ("httpx", "httpcore")}
    for name in saved:
        logging.getLogger(name).setLevel(logging.NOTSET)
    yield
    for name, level in saved.items():
        logging.getLogger(name).setLevel(level)
    sys.modules.pop("mcp_server", None)


def test_server_quiets_httpx_and_httpcore_itself(no_scraper_side_effect):
    _fresh_import()
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
    assert logging.getLogger("httpcore").getEffectiveLevel() >= logging.WARNING


def test_auth_token_never_reaches_the_log(no_scraper_side_effect, caplog):
    _fresh_import()
    # The import reconfigures logging with force=True, which drops caplog's handler.
    root = logging.getLogger()
    if caplog.handler not in root.handlers:
        root.addHandler(caplog.handler)
    caplog.set_level(logging.INFO)
    url = f"https://www.beeminder.com/api/v1/users/me/goals.json?auth_token={SECRET}&datapoints=true"
    logging.getLogger("httpx").info(f"HTTP Request: GET {url} \"HTTP/1.1 200 OK\"")
    logging.getLogger("mecris").info("Beeminder call %s", url)
    logging.getLogger("mecris.beeminder").warning(f"retrying {url}")
    assert SECRET not in caplog.text
    assert "auth_token=" not in caplog.text


def test_test_session_points_the_log_at_a_temp_file():
    configured = os.environ.get("MECRIS_LOG_FILE")
    assert configured, "tests/conftest.py must set MECRIS_LOG_FILE"
    assert Path(configured).resolve() != PROD_LOG.resolve()
    assert REPO / "logs" not in Path(configured).resolve().parents


def test_log_file_follows_mecris_log_file(tmp_path):
    target = tmp_path / "server.log"
    before = _digest(PROD_LOG)
    module = _fresh_import({"MECRIS_LOG_FILE": str(target)}, stub_scraper=False)
    try:
        file_handlers = [h for h in logging.getLogger().handlers
                         if isinstance(h, logging.FileHandler)]
        assert [Path(h.baseFilename) for h in file_handlers] == [target]
        logging.getLogger("mecris").error("log hygiene probe")
        for handler in file_handlers:
            handler.flush()
        assert "log hygiene probe" in target.read_text()
        assert _digest(PROD_LOG) == before
    finally:
        sys.modules.pop("mcp_server", None)
        assert module is not None
