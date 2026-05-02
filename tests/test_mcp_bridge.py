"""
Unit tests for mcp_bridge.py MCPBridge.handle_request() method.

All network I/O is mocked via unittest.mock.patch. No DB or network access required.
Groups:
  - TestHandleRequestInitialize (2): happy path, missing id
  - TestHandleRequestToolsList (4): success, HTTP error, request exception, JSON decode error, allowedTools format
  - TestHandleRequestToolsCall (4): success dict, success non-dict, request error, JSON decode error
  - TestHandleRequestUnknownMethod (1): method not found
  - TestHandleRequestTopLevelException (1): unexpected Exception in outer try
  - TestMCPBridgeInit (1): constructor defaults

Total: 16 tests
"""

import json
import pytest
from unittest.mock import MagicMock, patch
import requests

# Ensure mcp_bridge can be imported without starting a server
import sys
import importlib

# Import the module — start_server is NOT called at import time, only in run()
import mcp_bridge
from mcp_bridge import MCPBridge


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _bridge():
    """Return a MCPBridge instance without starting any subprocess."""
    b = MCPBridge.__new__(MCPBridge)
    b.server_process = None
    b.base_url = "http://localhost:8000"
    return b


def _req(method, req_id=1, params=None):
    r = {"jsonrpc": "2.0", "method": method, "id": req_id}
    if params is not None:
        r["params"] = params
    return r


# ---------------------------------------------------------------------------
# TestMCPBridgeInit
# ---------------------------------------------------------------------------

class TestMCPBridgeInit:
    def test_defaults(self):
        b = MCPBridge.__new__(MCPBridge)
        b.__init__()
        assert b.base_url == "http://localhost:8000"
        assert b.server_process is None


# ---------------------------------------------------------------------------
# TestHandleRequestInitialize
# ---------------------------------------------------------------------------

class TestHandleRequestInitialize:
    def test_initialize_returns_capabilities(self):
        b = _bridge()
        resp = b.handle_request(_req("initialize"))
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 1
        result = resp["result"]
        assert result["protocolVersion"] == "2024-11-05"
        assert "tools" in result["capabilities"]
        assert result["serverInfo"]["name"] == "mecris"

    def test_initialize_preserves_id(self):
        b = _bridge()
        resp = b.handle_request(_req("initialize", req_id=42))
        assert resp["id"] == 42


# ---------------------------------------------------------------------------
# TestHandleRequestToolsList
# ---------------------------------------------------------------------------

class TestHandleRequestToolsList:
    def test_tools_list_success(self):
        b = _bridge()
        tools = [{"name": "get_narrator_context", "description": "ctx", "inputSchema": {}}]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"tools": tools}

        with patch("requests.get", return_value=mock_resp):
            resp = b.handle_request(_req("tools/list"))

        assert resp["id"] == 1
        assert resp["result"]["tools"] == tools

    def test_tools_list_http_error(self):
        b = _bridge()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"

        with patch("requests.get", return_value=mock_resp):
            resp = b.handle_request(_req("tools/list"))

        assert "error" in resp
        assert resp["error"]["code"] == -32603
        assert "HTTP 500" in resp["error"]["message"]

    def test_tools_list_request_exception(self):
        b = _bridge()
        with patch("requests.get", side_effect=requests.RequestException("conn refused")):
            resp = b.handle_request(_req("tools/list"))

        assert "error" in resp
        assert resp["error"]["code"] == -32603
        assert "conn refused" in resp["error"]["message"]

    def test_tools_list_json_decode_error(self):
        b = _bridge()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.side_effect = json.JSONDecodeError("bad json", "", 0)
        mock_resp.text = "not json"

        with patch("requests.get", return_value=mock_resp):
            resp = b.handle_request(_req("tools/list"))

        assert "error" in resp
        assert resp["error"]["code"] == -32603
        assert "Invalid JSON" in resp["error"]["message"]

    def test_tools_list_bare_list_manifest(self):
        """Regression: server returns a bare JSON list instead of a dict — must not AttributeError."""
        b = _bridge()
        tools = [{"name": "ping", "description": "pong", "inputSchema": {}}]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = tools  # bare list, no .get()

        with patch("requests.get", return_value=mock_resp):
            resp = b.handle_request(_req("tools/list"))

        assert resp["id"] == 1
        assert resp["result"]["tools"] == tools

    def test_tools_list_allowed_tools_format(self):
        """allowedTools key triggers conversion to standard tool dicts."""
        b = _bridge()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"allowedTools": ["get_narrator_context", "get_budget_status"]}

        with patch("requests.get", return_value=mock_resp):
            resp = b.handle_request(_req("tools/list"))

        tools = resp["result"]["tools"]
        assert len(tools) == 2
        names = {t["name"] for t in tools}
        assert names == {"get_narrator_context", "get_budget_status"}


# ---------------------------------------------------------------------------
# TestHandleRequestToolsCall
# ---------------------------------------------------------------------------

class TestHandleRequestToolsCall:
    def _call_req(self, tool_name="get_narrator_context", arguments=None, req_id=1):
        return _req("tools/call", req_id=req_id, params={
            "name": tool_name,
            "arguments": arguments or {}
        })

    def test_tools_call_success_dict(self):
        b = _bridge()
        result_data = {"status": "ok", "message": "hello"}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": result_data}

        with patch("requests.post", return_value=mock_resp):
            resp = b.handle_request(self._call_req())

        assert resp["id"] == 1
        content = resp["result"]["content"]
        assert len(content) == 1
        assert content[0]["type"] == "text"
        # result_data should be serialized as JSON
        parsed = json.loads(content[0]["text"])
        assert parsed == result_data

    def test_tools_call_success_non_dict(self):
        b = _bridge()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": "plain string result"}

        with patch("requests.post", return_value=mock_resp):
            resp = b.handle_request(self._call_req())

        content = resp["result"]["content"]
        assert content[0]["text"] == "plain string result"

    def test_tools_call_http_error(self):
        b = _bridge()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = "Not Found"

        with patch("requests.post", return_value=mock_resp):
            resp = b.handle_request(self._call_req())

        assert "error" in resp
        assert resp["error"]["code"] == -32603
        assert "HTTP 404" in resp["error"]["message"]

    def test_tools_call_request_exception(self):
        b = _bridge()
        with patch("requests.post", side_effect=requests.RequestException("timeout")):
            resp = b.handle_request(self._call_req())

        assert "error" in resp
        assert resp["error"]["code"] == -32603
        assert "timeout" in resp["error"]["message"]

    def test_tools_call_json_decode_error(self):
        b = _bridge()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.side_effect = json.JSONDecodeError("bad", "", 0)
        mock_resp.text = "garbage"

        with patch("requests.post", return_value=mock_resp):
            resp = b.handle_request(self._call_req())

        assert "error" in resp
        assert resp["error"]["code"] == -32603
        assert "Invalid JSON" in resp["error"]["message"]

    def test_tools_call_preserves_id(self):
        b = _bridge()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": {}}

        with patch("requests.post", return_value=mock_resp):
            resp = b.handle_request(self._call_req(req_id=99))

        assert resp["id"] == 99


# ---------------------------------------------------------------------------
# TestHandleRequestUnknownMethod
# ---------------------------------------------------------------------------

class TestHandleRequestUnknownMethod:
    def test_unknown_method_returns_method_not_found(self):
        b = _bridge()
        resp = b.handle_request(_req("notifications/initialized"))
        assert "error" in resp
        assert resp["error"]["code"] == -32601
        assert "Method not found" in resp["error"]["message"]


# ---------------------------------------------------------------------------
# TestHandleRequestTopLevelException
# ---------------------------------------------------------------------------

class TestHandleRequestTopLevelException:
    def test_outer_exception_caught(self):
        """An exception raised inside handle_request is caught by the outer handler.

        The outer except block calls request.get("id"), so the mock must allow
        that call to succeed while making request.get("method") raise.
        """
        b = _bridge()

        def _get_side_effect(key, default=None):
            if key == "method":
                raise RuntimeError("unexpected failure")
            return None  # id → None is fine for error response

        bad_req = MagicMock()
        bad_req.get.side_effect = _get_side_effect

        resp = b.handle_request(bad_req)
        assert "error" in resp
        assert resp["error"]["code"] == -32603
        assert "unexpected failure" in resp["error"]["message"]
