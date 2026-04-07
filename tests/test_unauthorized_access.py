import pytest
from fastapi.testclient import TestClient
from mcp_server import app
import os
from unittest.mock import patch

# Verify that the FastAPI endpoints in mcp_server.py require authentication
# when NOT in standalone mode.

@pytest.fixture
def client():
    with patch.dict(os.environ, {"MECRIS_MODE": "cloud", "DEFAULT_USER_ID": ""}):
        return TestClient(app)

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
