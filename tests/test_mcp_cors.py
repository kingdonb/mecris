import pytest
from fastapi.testclient import TestClient
from mcp_server import app

client = TestClient(app)

def test_cors_preflight():
    # Simulate an OPTIONS request from a valid origin
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        }
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "GET" in response.headers.get("access-control-allow-methods", "")

def test_cors_get_health():
    # Simulate a GET request with an Origin header
    response = client.get(
        "/health",
        headers={"Origin": "http://localhost:5173"}
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"

def test_cors_invalid_origin():
    # Simulate a request from an invalid origin
    response = client.get(
        "/health",
        headers={"Origin": "http://malicious.com"}
    )
    # FastAPI's CORSMiddleware doesn't necessarily block the request,
    # but it shouldn't return the CORS headers for unauthorized origins.
    assert response.headers.get("access-control-allow-origin") is None
