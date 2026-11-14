import os

# Keep the test session off live services. This must run before any project
# import: beeminder_client, twilio_sender and others call a bare load_dotenv()
# at import, which walks up from the module's directory. A worktree under the
# user's checkout then found the checkout's real .env, and importing
# mcp_server ran DDL against live Neon. dotenv is made a no-op and live
# credentials are stripped from the environment. MECRIS_TESTS_USE_ENV=1 opts
# back in for deliberate live runs.
_LIVE_KEYS = ("NEON_DB_URL", "DATABASE_URL", "CLAUDE_API_KEY")
_LIVE_PREFIXES = ("TWILIO_", "BEEMINDER_", "ANTHROPIC_", "OPENROUTER_", "GROQ_")

if os.environ.get("MECRIS_TESTS_USE_ENV") != "1":
    import dotenv
    import dotenv.main

    def _dotenv_disabled(*args, **kwargs):
        return False

    dotenv.load_dotenv = _dotenv_disabled
    dotenv.main.load_dotenv = _dotenv_disabled
    for _key in [k for k in os.environ if k in _LIVE_KEYS or k.startswith(_LIVE_PREFIXES)]:
        del os.environ[_key]

import tempfile
import pytest
import types
import requests

# mcp_server attaches a file handler at import. Point it at a per-run temp file
# so the test session never writes into the production logs/mecris_server.log.
os.environ["MECRIS_LOG_FILE"] = os.path.join(
    tempfile.mkdtemp(prefix="mecris-pytest-logs-"), "mecris_server.log"
)

# Pre-load real packages into sys.modules so that later test files using
# sys.modules.setdefault("psycopg2", MagicMock()) are no-ops and don't
# poison the module cache for tests that need the real implementations.
import psycopg2            # noqa: F401
import psycopg2.extras     # noqa: F401
import apscheduler                       # noqa: F401
import apscheduler.jobstores            # noqa: F401
import apscheduler.jobstores.memory     # noqa: F401
import apscheduler.jobstores.sqlalchemy # noqa: F401
import apscheduler.schedulers          # noqa: F401
import apscheduler.schedulers.asyncio  # noqa: F401
import apscheduler.triggers            # noqa: F401
import apscheduler.triggers.date       # noqa: F401

class DummyResponse:
    def __init__(self, json_data=None, status_code=200):
        self._json = json_data or {}
        self.status_code = status_code
    def json(self):
        return self._json

@pytest.fixture
def method():
    """Default delivery method fixture used by delivery tests."""
    return "console"

@pytest.fixture
def message():
    """Default message fixture used by reminder system tests."""
    return "Test message"

@pytest.fixture(autouse=True)
def mock_requests(monkeypatch):
    """Mock HTTP endpoints used by the MCP server.
    This avoids the need for a running MCP process during unit testing.
    """
    def mock_post(url, json=None, **kwargs):
        if "intelligent-reminder/send" in url:
            # Simulate a successful send response
            return DummyResponse({
                "sent": True,
                "delivery_method": json.get("type", "unknown"),
                "delivery_details": {
                    "attempts": [{"method": json.get("type", "unknown"), "success": True}]
                }
            })
        if "sms-consent/opt-in" in url:
            return DummyResponse({"success": True})
        if "intelligent-reminder/trigger" in url:
            return DummyResponse({"triggered": True})
        # Fallback generic response
        return DummyResponse({})

    def mock_get(url, **kwargs):
        if "sms-consent/status" in url:
            return DummyResponse({"found": True, "opted_in": True})
        if "sms-consent/summary" in url:
            return DummyResponse({"summary": {"total_users": 1, "opted_in": 1}})
        if "intelligent-reminder/check" in url:
            return DummyResponse({"should_send": True, "tier": "base_mode", "reason": "test"})
        # Default empty response
        return DummyResponse({})

    monkeypatch.setattr(requests, "post", mock_post)
    monkeypatch.setattr(requests, "get", mock_get)


_NEON_REQUIRED = {"test_standalone_access.py", "test_unauthorized_access.py", "test_mcp_cors.py", "test_usage_tracker.py"}


def pytest_ignore_collect(collection_path, config):
    """Skip test files that require a live NEON_DB_URL when the env var is absent."""
    if not os.environ.get("NEON_DB_URL") and collection_path.name in _NEON_REQUIRED:
        return True


@pytest.fixture(autouse=True)
def mock_usage_tracker_init(monkeypatch):
    """When NEON_DB_URL is absent, prevent UsageTracker from raising at instantiation.

    Resets the module-level singleton and mocks init_database to a no-op so that
    get_tracker() succeeds without a live Neon connection. Tests that need specific
    return values from tracker methods (e.g. get_user_preferences) already patch
    those methods themselves; this fixture only removes the init-time barrier.
    """
    if not os.environ.get("NEON_DB_URL"):
        import usage_tracker as _ut
        monkeypatch.setattr(_ut, "_tracker_instance", None)
        monkeypatch.setattr(_ut.UsageTracker, "init_database", lambda self: None)
