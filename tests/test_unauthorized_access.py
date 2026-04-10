import pytest
import sys
import os
from unittest.mock import patch


def _make_mcp_importable(mode="cloud"):
    """Patch env + psycopg2 so mcp_server can be imported without a real DB."""
    return [
        patch.dict("os.environ", {
            "NEON_DB_URL": "postgres://fake",
            "DEFAULT_USER_ID": "",
            "MECRIS_MODE": mode,
        }),
        patch("psycopg2.connect"),
    ]


@pytest.fixture
def client():
    sys.modules.pop("mcp_server", None)
    env_patch, db_patch = _make_mcp_importable("cloud")
    with env_patch, db_patch:
        from mcp_server import app
        from fastapi.testclient import TestClient
        yield TestClient(app)
    sys.modules.pop("mcp_server", None)


# Verify that the FastAPI endpoints in mcp_server.py require authentication
# when NOT in standalone mode.

def test_narrator_context_no_auth(client):
    """Verify that /narrator/context REJECTS requests without authentication."""
    response = client.get("/narrator/context")
    assert response.status_code == 401, "Endpoint should REQUIRE authentication"

def test_beeminder_status_no_auth(client):
    """Verify that /beeminder/status REJECTS requests without authentication."""
    response = client.get("/beeminder/status")
    assert response.status_code == 401, "Endpoint should REQUIRE authentication"

def test_budget_status_no_auth(client):
    """Verify that /budget/status REJECTS requests without authentication."""
    response = client.get("/budget/status")
    assert response.status_code == 401, "Endpoint should REQUIRE authentication"
