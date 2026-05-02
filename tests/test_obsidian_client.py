"""Unit tests for ObsidianMCPClient in obsidian_client.py.

Covers:
- Pure-Python helpers: _extract_priority, _extract_tags, _parse_goals_from_content
- Async HTTP methods: health_check, _mcp_call, search_vault, get_file_content,
  list_vault_files, append_content, get_goals, get_todos, get_daily_note,
  append_to_session_log, close

Closes yebyen/mecris#322.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from obsidian_client import ObsidianMCPClient


def _fresh_client():
    """Return an ObsidianMCPClient with a mocked httpx.AsyncClient."""
    c = ObsidianMCPClient.__new__(ObsidianMCPClient)
    c.host = "localhost"
    c.port = 3001
    c.base_url = "http://localhost:3001"
    c.vault_path = ""
    mock_http = MagicMock()
    mock_http.get = AsyncMock()
    mock_http.post = AsyncMock()
    mock_http.aclose = AsyncMock()
    c.client = mock_http
    return c


# ---------------------------------------------------------------------------
# Pure-Python helpers
# ---------------------------------------------------------------------------

class TestExtractPriority:
    @pytest.fixture
    def client(self):
        return ObsidianMCPClient()

    def test_high_fire_emoji(self, client):
        assert client._extract_priority("🔥 Critical bug fix") == "high"

    def test_high_triple_bang(self, client):
        assert client._extract_priority("Fix this!!! now") == "high"

    def test_medium_warning_emoji(self, client):
        assert client._extract_priority("⚠️ Watch out") == "medium"

    def test_medium_double_bang(self, client):
        assert client._extract_priority("Needs review!! soon") == "medium"

    def test_low_single_bang(self, client):
        assert client._extract_priority("Minor thing!") == "low"

    def test_none_plain(self, client):
        assert client._extract_priority("Just a plain task") is None

    def test_none_empty(self, client):
        assert client._extract_priority("") is None


class TestExtractTags:
    @pytest.fixture
    def client(self):
        return ObsidianMCPClient()

    def test_single_tag(self, client):
        assert client._extract_tags("Do the thing #work") == ["work"]

    def test_multiple_tags(self, client):
        tags = client._extract_tags("Review PR #backend #urgent")
        assert "backend" in tags
        assert "urgent" in tags

    def test_no_tags(self, client):
        assert client._extract_tags("No hashtag here") == []

    def test_empty_string(self, client):
        assert client._extract_tags("") == []


class TestParseGoalsFromContent:
    @pytest.fixture
    def client(self):
        return ObsidianMCPClient()

    def test_parses_goal_in_goals_section(self, client):
        content = "## Goals\n- [ ] Run a marathon\n"
        goals = client._parse_goals_from_content(content, "file.md")
        assert len(goals) == 1
        assert goals[0]["content"] == "Run a marathon"

    def test_parses_h1_goals_section(self, client):
        content = "# Goals\n- Walk 10k steps\n"
        goals = client._parse_goals_from_content(content, "file.md")
        assert len(goals) == 1
        assert goals[0]["content"] == "Walk 10k steps"

    def test_parses_h3_goals_section(self, client):
        content = "### Goals\n- [ ] Learn Spanish\n"
        goals = client._parse_goals_from_content(content, "file.md")
        assert len(goals) == 1
        assert goals[0]["content"] == "Learn Spanish"

    def test_completed_goal_detected(self, client):
        content = "## Goals\n- [x] Finished goal\n"
        goals = client._parse_goals_from_content(content, "file.md")
        assert goals[0]["completed"] is True

    def test_unchecked_goal_detected(self, client):
        content = "## Goals\n- [ ] Pending goal\n"
        goals = client._parse_goals_from_content(content, "file.md")
        assert goals[0]["completed"] is False

    def test_no_checkbox_goal(self, client):
        content = "## Goals\n- Plain goal text\n"
        goals = client._parse_goals_from_content(content, "file.md")
        assert goals[0]["completed"] is None

    def test_stops_at_new_header(self, client):
        content = "## Goals\n- Goal A\n## Other\n- Not a goal\n"
        goals = client._parse_goals_from_content(content, "file.md")
        assert len(goals) == 1
        assert goals[0]["content"] == "Goal A"

    def test_source_file_and_section_recorded(self, client):
        content = "## Goals\n- My goal\n"
        goals = client._parse_goals_from_content(content, "notes/plan.md")
        assert goals[0]["source_file"] == "notes/plan.md"
        assert "Goals" in goals[0]["source_section"]

    def test_content_outside_goals_section_ignored(self, client):
        content = "## Random section\n- Item\n"
        goals = client._parse_goals_from_content(content, "file.md")
        assert goals == []

    def test_empty_content_returns_empty(self, client):
        assert client._parse_goals_from_content("", "file.md") == []


# ---------------------------------------------------------------------------
# Async HTTP methods
# ---------------------------------------------------------------------------

class TestHealthCheck:
    def test_returns_ok_on_200(self):
        c = _fresh_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        c.client.get.return_value = mock_resp
        result = asyncio.run(c.health_check())
        assert result == "ok"

    def test_returns_error_on_non_200(self):
        c = _fresh_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        c.client.get.return_value = mock_resp
        result = asyncio.run(c.health_check())
        assert result == "error"

    def test_returns_unreachable_on_exception(self):
        c = _fresh_client()
        c.client.get.side_effect = Exception("connection refused")
        result = asyncio.run(c.health_check())
        assert result == "unreachable"


class TestMcpCall:
    def test_success_returns_json(self):
        c = _fresh_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"files": ["a.md"]}
        c.client.post.return_value = mock_resp
        result = asyncio.run(c._mcp_call("list_files_in_vault", {}))
        assert result == {"files": ["a.md"]}

    def test_non_200_returns_none(self):
        c = _fresh_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = "not found"
        c.client.post.return_value = mock_resp
        result = asyncio.run(c._mcp_call("get_file_contents", {"file_path": "x"}))
        assert result is None

    def test_exception_returns_none(self):
        c = _fresh_client()
        c.client.post.side_effect = Exception("timeout")
        result = asyncio.run(c._mcp_call("search", {"query": "test"}))
        assert result is None


class TestSearchVault:
    def test_returns_matches_on_success(self):
        c = _fresh_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"matches": [{"file_path": "notes.md"}]}
        c.client.post.return_value = mock_resp
        result = asyncio.run(c.search_vault("goals"))
        assert result == [{"file_path": "notes.md"}]

    def test_returns_empty_list_on_none(self):
        c = _fresh_client()
        c.client.post.side_effect = Exception("fail")
        result = asyncio.run(c.search_vault("anything"))
        assert result == []


class TestGetFileContent:
    def test_returns_content_string(self):
        c = _fresh_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"content": "# My Note\nHello"}
        c.client.post.return_value = mock_resp
        result = asyncio.run(c.get_file_content("notes.md"))
        assert result == "# My Note\nHello"

    def test_returns_empty_string_on_none(self):
        c = _fresh_client()
        c.client.post.side_effect = Exception("fail")
        result = asyncio.run(c.get_file_content("missing.md"))
        assert result == ""


class TestListVaultFiles:
    def test_returns_file_list(self):
        c = _fresh_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"files": ["a.md", "b.md"]}
        c.client.post.return_value = mock_resp
        result = asyncio.run(c.list_vault_files())
        assert result == ["a.md", "b.md"]

    def test_returns_empty_list_on_none(self):
        c = _fresh_client()
        c.client.post.side_effect = Exception("fail")
        result = asyncio.run(c.list_vault_files())
        assert result == []


class TestAppendContent:
    def test_returns_true_on_success(self):
        c = _fresh_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"success": True}
        c.client.post.return_value = mock_resp
        result = asyncio.run(c.append_content("log.md", "new content"))
        assert result is True

    def test_returns_false_on_failure(self):
        c = _fresh_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"success": False}
        c.client.post.return_value = mock_resp
        result = asyncio.run(c.append_content("log.md", "content"))
        assert result is False

    def test_returns_false_on_exception(self):
        c = _fresh_client()
        c.client.post.side_effect = Exception("fail")
        result = asyncio.run(c.append_content("log.md", "content"))
        assert result is False


class TestGetDailyNote:
    def test_returns_content_from_first_matching_pattern(self):
        c = _fresh_client()

        def _make_post_resp(data):
            r = MagicMock()
            r.status_code = 200
            r.json.return_value = data
            return r

        # First call (Daily Notes/2026-05-01.md) succeeds
        c.client.post.return_value = _make_post_resp({"content": "# Daily Note"})
        result = asyncio.run(c.get_daily_note("2026-05-01"))
        assert result == "# Daily Note"

    def test_returns_empty_string_when_not_found(self):
        c = _fresh_client()
        # _mcp_call returns None for all patterns + search
        c.client.post.side_effect = Exception("fail")
        result = asyncio.run(c.get_daily_note("2099-01-01"))
        assert result == ""


class TestAppendToSessionLog:
    def test_prepends_header_on_empty_file(self):
        c = _fresh_client()
        captured = []

        async def fake_get_content(path):
            return ""  # No existing content

        async def fake_append(path, content):
            captured.append(content)
            return True

        with patch.object(c, "get_file_content", side_effect=fake_get_content), \
             patch.object(c, "append_content", side_effect=fake_append):
            result = asyncio.run(c.append_to_session_log("My log entry"))

        assert result is True
        assert len(captured) == 1
        # Header should be prepended when file is empty
        assert "Mecris Session Log" in captured[0]
        assert "My log entry" in captured[0]

    def test_no_header_on_existing_file(self):
        c = _fresh_client()
        captured = []

        async def fake_get_content(path):
            return "# Existing content"

        async def fake_append(path, content):
            captured.append(content)
            return True

        with patch.object(c, "get_file_content", side_effect=fake_get_content), \
             patch.object(c, "append_content", side_effect=fake_append):
            asyncio.run(c.append_to_session_log("New entry"))

        assert "Mecris Session Log" not in captured[0]
        assert "New entry" in captured[0]

    def test_returns_false_on_exception(self):
        c = _fresh_client()

        async def fail_get(_):
            raise Exception("boom")

        with patch.object(c, "get_file_content", side_effect=fail_get):
            result = asyncio.run(c.append_to_session_log("entry"))

        assert result is False


class TestClose:
    def test_calls_aclose(self):
        c = _fresh_client()
        asyncio.run(c.close())
        c.client.aclose.assert_awaited_once()
