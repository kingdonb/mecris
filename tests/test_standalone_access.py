import pytest
from fastapi.testclient import TestClient
from mcp_server import app
import os
from unittest.mock import patch

# Verify that the FastAPI endpoints in mcp_server.py ALLOW access
# without tokens when in STANDALONE mode.

def test_narrator_context_standalone():
    """Verify that /narrator/context ALLOWS access in standalone mode."""
    with patch.dict(os.environ, {"MECRIS_MODE": "standalone"}):
        # We need to re-read the environment variable if the app uses it at runtime
        # but mcp_server checks it inside the dependency/handler usually.
        client = TestClient(app)
        response = client.get("/narrator/context")
        assert response.status_code == 200
        print("\n✅ [PASS] /narrator/context allowed access in standalone mode.")

def test_health_check_public():
    """Verify that /health is always public."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    print("✅ [PASS] /health is public.")
