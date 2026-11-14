"""Bridge exposure tests (#39, narrowed).

The FastAPI bridge in mcp_server.py must not hand the default user to LAN
callers. These tests pin three properties:

1. The MCP SSE app is not mounted under /mcp (it exposed every tool without
   credentials).
2. The bridge binds to MECRIS_BRIDGE_HOST, defaulting to 127.0.0.1.
3. The standalone fallback to the default user applies only to loopback
   clients; anyone else needs a valid bearer token.
"""
import sys
import time
from unittest.mock import AsyncMock, patch

import jwt
import pytest

LOOPBACK_V4 = ("127.0.0.1", 50000)
LOOPBACK_V6 = ("::1", 50000)
LAN_CLIENT = ("192.168.1.50", 50000)


def _env(mode="standalone", **extra):
    env = {
        "NEON_DB_URL": "postgres://fake",
        "DEFAULT_USER_ID": "test-user",
        "MECRIS_MODE": mode,
    }
    env.update(extra)
    return env


@pytest.fixture
def server_module():
    """Import a fresh mcp_server with a fake DB and standalone mode."""
    sys.modules.pop("mcp_server", None)
    with patch.dict("os.environ", _env()), patch("psycopg2.connect"):
        import mcp_server
        # Keep handlers inert: no local credentials file, no network, no DB work.
        with patch.object(mcp_server.credentials_manager, "resolve_user_id", return_value="default-user"), \
             patch.object(mcp_server, "get_budget_status", return_value={"ok": True}), \
             patch.object(mcp_server, "_run_cloud_sync_background", new=AsyncMock()):
            yield mcp_server
    sys.modules.pop("mcp_server", None)


def _client(module, client_addr):
    from fastapi.testclient import TestClient
    return TestClient(module.app, client=client_addr, raise_server_exceptions=False)


def _unsigned_token(sub="token-user"):
    # Standalone mode checks expiry only, so an HS256 token is enough here.
    return jwt.encode({"sub": sub, "exp": int(time.time()) + 600}, "test-secret", algorithm="HS256")


# --- 1. /mcp is not mounted -------------------------------------------------

def test_mcp_sse_app_is_not_mounted(server_module):
    paths = [getattr(r, "path", "") for r in server_module.app.routes]
    assert not any(p == "/mcp" or p.startswith("/mcp/") for p in paths), paths


def test_mcp_sse_endpoint_is_not_found(server_module):
    response = _client(server_module, LOOPBACK_V4).get("/mcp/sse")
    assert response.status_code == 404


# --- 2. Bind host -----------------------------------------------------------

def test_bridge_binds_loopback_by_default(server_module, monkeypatch):
    monkeypatch.delenv("MECRIS_BRIDGE_HOST", raising=False)
    with patch("uvicorn.run") as run:
        server_module.run_http_bridge()
    assert run.call_args.kwargs["host"] == "127.0.0.1"
    assert run.call_args.kwargs["port"] == 8080


def test_bridge_host_is_configurable(server_module, monkeypatch):
    monkeypatch.setenv("MECRIS_BRIDGE_HOST", "0.0.0.0")
    with patch("uvicorn.run") as run:
        server_module.run_http_bridge()
    assert run.call_args.kwargs["host"] == "0.0.0.0"


def test_blank_bridge_host_falls_back_to_loopback(server_module, monkeypatch):
    monkeypatch.setenv("MECRIS_BRIDGE_HOST", "  ")
    with patch("uvicorn.run") as run:
        server_module.run_http_bridge()
    assert run.call_args.kwargs["host"] == "127.0.0.1"


# --- 3. Standalone fallback is loopback-only --------------------------------

@pytest.mark.parametrize("path", ["/profile", "/budget/status"])
def test_lan_client_without_token_is_rejected(server_module, path):
    response = _client(server_module, LAN_CLIENT).get(path)
    assert response.status_code == 401


@pytest.mark.parametrize("path", [
    "/internal/log-message",
    "/internal/cloud-sync",
    "/internal/confirm-phone-verification",
])
def test_lan_client_without_token_is_rejected_on_internal(server_module, path):
    response = _client(server_module, LAN_CLIENT).post(path, json={})
    assert response.status_code == 401


def test_non_ip_client_without_token_is_rejected(server_module):
    # Starlette's TestClient default peer is the string "testclient".
    response = _client(server_module, ("testclient", 50000)).get("/budget/status")
    assert response.status_code == 401


@pytest.mark.parametrize("addr", [LOOPBACK_V4, LOOPBACK_V6])
def test_loopback_client_resolves_default_user(server_module, addr):
    response = _client(server_module, addr).post("/internal/log-message", json={})
    assert response.status_code == 200


def test_loopback_fallback_returns_default_user(server_module):
    response = _client(server_module, LOOPBACK_V4).get("/budget/status")
    assert response.status_code == 200
    server_module.get_budget_status.assert_called_once_with("default-user")


def test_lan_client_with_valid_token_is_accepted(server_module):
    headers = {"Authorization": f"Bearer {_unsigned_token()}"}
    response = _client(server_module, LAN_CLIENT).get("/budget/status", headers=headers)
    assert response.status_code == 200
    server_module.get_budget_status.assert_called_once_with("token-user")


def test_spoofed_host_header_does_not_grant_loopback(server_module):
    response = _client(server_module, LAN_CLIENT).get(
        "/budget/status", headers={"Host": "localhost:8080"}
    )
    assert response.status_code == 401
