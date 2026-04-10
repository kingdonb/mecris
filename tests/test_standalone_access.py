import pytest
import sys
import os
from unittest.mock import patch


def _make_mcp_importable(mode="standalone"):
    """Patch env + psycopg2 so mcp_server can be imported without a real DB."""
    return [
        patch.dict("os.environ", {
            "NEON_DB_URL": "postgres://fake",
            "DEFAULT_USER_ID": "test-user",
            "MECRIS_MODE": mode,
        }),
        patch("psycopg2.connect"),
    ]


@pytest.fixture
def standalone_client():
    sys.modules.pop("mcp_server", None)
    env_patch, db_patch = _make_mcp_importable("standalone")
    with env_patch, db_patch:
        from mcp_server import app
        from fastapi.testclient import TestClient
        yield TestClient(app)
    sys.modules.pop("mcp_server", None)


# Verify that the FastAPI endpoints in mcp_server.py ALLOW access
# without tokens when in STANDALONE mode.

def test_narrator_context_standalone(standalone_client):
    """Verify that /narrator/context ALLOWS access in standalone mode."""
    response = standalone_client.get("/narrator/context")
    assert response.status_code == 200

def test_health_check_public(standalone_client):
    """Verify that /health is always public."""
    response = standalone_client.get("/health")
    assert response.status_code == 200
