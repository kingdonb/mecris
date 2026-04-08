import os
import pytest
import types
import requests

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


_NEON_REQUIRED = {"test_standalone_access.py", "test_unauthorized_access.py"}


def pytest_ignore_collect(collection_path, config):
    """Skip test files that require a live NEON_DB_URL when the env var is absent."""
    if not os.environ.get("NEON_DB_URL") and collection_path.name in _NEON_REQUIRED:
        return True
