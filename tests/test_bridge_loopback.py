"""Bridge exposure tests (#39, narrowed).

The FastAPI bridge in mcp_server.py must not hand the default user to LAN
callers or to web pages. These tests pin four properties:

1. The MCP SSE app is not mounted under /mcp (it exposed every tool without
   credentials).
2. The bridge binds to MECRIS_BRIDGE_HOST, defaulting to 127.0.0.1.
3. The standalone fallback to the default user applies only to trusted local
   requests: a loopback peer whose Host is a loopback name and whose Origin,
   if any, is the local web UI. A page in the user's browser cannot borrow
   the fallback through cross-site requests (CSRF) or DNS rebinding.
4. Every other caller needs a bearer token whose signature checks out
   against the Pocket ID JWKS, even in standalone mode (standalone
   verify_token in services/auth_service.py skips the signature check).
"""
import sys
import time
from unittest.mock import AsyncMock, patch

import jwt
import pytest

LOOPBACK_V4 = ("127.0.0.1", 50000)
LOOPBACK_V6 = ("::1", 50000)
LAN_CLIENT = ("192.168.1.50", 50000)
ISSUER = "https://issuer.test"


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


def _client(module, client_addr, base_url="http://localhost:8080"):
    from fastapi.testclient import TestClient
    return TestClient(module.app, client=client_addr, base_url=base_url,
                      raise_server_exceptions=False)


def _rsa_key():
    from cryptography.hazmat.primitives.asymmetric import rsa
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


_TRUSTED_KEY = _rsa_key()
_FOREIGN_KEY = _rsa_key()


def _claims(sub):
    return {"sub": sub, "iss": ISSUER, "exp": int(time.time()) + 600}


def _signed_token(sub="token-user", key=_TRUSTED_KEY):
    return jwt.encode(_claims(sub), key, algorithm="RS256")


def _unsigned_token(sub="token-user"):
    # A forged token: HS256 with a key the caller picked.
    return jwt.encode(_claims(sub), "test-secret", algorithm="HS256")


def _alg_none_token(sub="token-user"):
    return jwt.encode(_claims(sub), None, algorithm="none")


def _foreign_key_token(sub="token-user"):
    return _signed_token(sub, key=_FOREIGN_KEY)


@pytest.fixture
def trusted_jwks(monkeypatch):
    """Stand-in JWKS client that knows only _TRUSTED_KEY (no network)."""
    from services import auth_service

    class _Key:
        key = _TRUSTED_KEY.public_key()

    class _FakeJwks:
        def get_signing_key_from_jwt(self, token):
            return _Key()

    monkeypatch.setenv("OIDC_ISSUER", ISSUER)
    monkeypatch.setattr(auth_service, "_jwks_client", _FakeJwks())


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


# --- 3. Standalone fallback is local-only -----------------------------------

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


@pytest.mark.parametrize("host", [
    "127.0.0.1:8080", "[::1]:8080", "localhost", "LOCALHOST:8080",
])
def test_loopback_host_names_resolve_default_user(server_module, host):
    response = _client(server_module, LOOPBACK_V4).get(
        "/budget/status", headers={"Host": host}
    )
    assert response.status_code == 200


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:5173"])
def test_local_web_ui_origin_resolves_default_user(server_module, origin):
    response = _client(server_module, LOOPBACK_V4).get(
        "/budget/status", headers={"Origin": origin, "Sec-Fetch-Site": "same-site"}
    )
    assert response.status_code == 200
    server_module.get_budget_status.assert_called_once_with("default-user")


def test_spoofed_host_header_does_not_grant_loopback(server_module):
    response = _client(server_module, LAN_CLIENT).get(
        "/budget/status", headers={"Host": "localhost:8080"}
    )
    assert response.status_code == 401


# --- 4. Browser attacks on the loopback fallback ----------------------------

def test_dns_rebound_host_does_not_get_default_user(server_module):
    # DNS rebinding: the peer is loopback but Host is the attacker's name.
    response = _client(server_module, LOOPBACK_V4).get(
        "/budget/status", headers={"Host": "rebind.attacker.example:8080"}
    )
    assert response.status_code == 401
    server_module.get_budget_status.assert_not_called()


def test_cross_site_origin_does_not_get_default_user(server_module):
    # CSRF: a simple cross-site POST from a page in the user's browser.
    with patch.object(server_module, "trigger_reminder_check",
                           new=AsyncMock(return_value={"ok": True})) as trigger:
        response = _client(server_module, LOOPBACK_V4).post(
            "/intelligent-reminder/trigger", headers={"Origin": "http://evil.example"}
        )
    assert response.status_code == 401
    trigger.assert_not_awaited()


def test_null_origin_does_not_get_default_user(server_module):
    response = _client(server_module, LOOPBACK_V4).post(
        "/internal/log-message", content=b"{}", headers={"Origin": "null"}
    )
    assert response.status_code == 401


def test_cross_site_fetch_metadata_does_not_get_default_user(server_module):
    # <img src=...>-style GET: no Origin header, but Sec-Fetch-Site says cross-site.
    response = _client(server_module, LOOPBACK_V4).get(
        "/budget/status", headers={"Sec-Fetch-Site": "cross-site"}
    )
    assert response.status_code == 401
    server_module.get_budget_status.assert_not_called()


def test_rebound_page_cannot_use_forged_token(server_module):
    # After rebinding, the page is same-origin and can set Authorization itself.
    response = _client(server_module, LOOPBACK_V4).get(
        "/budget/status",
        headers={"Host": "rebind.attacker.example:8080",
                 "Authorization": f"Bearer {_unsigned_token('default-user')}"},
    )
    assert response.status_code == 401
    server_module.get_budget_status.assert_not_called()


# --- 5. Non-local callers need a signature-checked token --------------------

def test_lan_client_with_jwks_signed_token_is_accepted(server_module, trusted_jwks):
    headers = {"Authorization": f"Bearer {_signed_token()}"}
    response = _client(server_module, LAN_CLIENT).get("/budget/status", headers=headers)
    assert response.status_code == 200
    server_module.get_budget_status.assert_called_once_with("token-user")


@pytest.mark.parametrize("make_token", [
    _unsigned_token, _alg_none_token, _foreign_key_token,
], ids=["hs256-forged", "alg-none", "foreign-rsa-key"])
def test_lan_client_with_forged_token_is_rejected(server_module, trusted_jwks, make_token):
    headers = {"Authorization": f"Bearer {make_token()}"}
    response = _client(server_module, LAN_CLIENT).get("/budget/status", headers=headers)
    assert response.status_code == 401
    server_module.get_budget_status.assert_not_called()


def test_lan_client_with_wrong_issuer_is_rejected(server_module, trusted_jwks, monkeypatch):
    monkeypatch.setenv("OIDC_ISSUER", "https://someone-else.test")
    headers = {"Authorization": f"Bearer {_signed_token()}"}
    response = _client(server_module, LAN_CLIENT).get("/budget/status", headers=headers)
    assert response.status_code == 401
    server_module.get_budget_status.assert_not_called()


def test_lan_client_token_rejected_when_jwks_unreachable(server_module, monkeypatch):
    from services import auth_service

    class _DownJwks:
        def get_signing_key_from_jwt(self, token):
            raise jwt.PyJWKClientError("unreachable")

    monkeypatch.setattr(auth_service, "_jwks_client", _DownJwks())
    headers = {"Authorization": f"Bearer {_signed_token()}"}
    response = _client(server_module, LAN_CLIENT).get("/budget/status", headers=headers)
    assert response.status_code == 401
    server_module.get_budget_status.assert_not_called()
