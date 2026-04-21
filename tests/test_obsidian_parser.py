"""
Unit tests for ObsidianMCPClient._parse_todos_from_content

Covers standard checkboxes ([ ], [x]) and alternate Obsidian theme styles
([>], [<], [?], [-], [!], etc.) per kingdonb/mecris#196.
"""

import pytest
from obsidian_client import ObsidianMCPClient


@pytest.fixture
def client():
    return ObsidianMCPClient()


def parse(client, text):
    """Helper: parse multi-line markdown and return todos list."""
    return client._parse_todos_from_content(text, "test.md")


class TestStandardCheckboxes:
    def test_pending_todo(self, client):
        todos = parse(client, "- [ ] Buy groceries")
        assert len(todos) == 1
        t = todos[0]
        assert t["content"] == "Buy groceries"
        assert t["status"] == " "
        assert t["completed"] is False

    def test_completed_todo_lowercase(self, client):
        todos = parse(client, "- [x] Walk the dogs")
        assert len(todos) == 1
        t = todos[0]
        assert t["status"] == "x"
        assert t["completed"] is True

    def test_completed_todo_uppercase(self, client):
        todos = parse(client, "- [X] Walk the dogs")
        assert len(todos) == 1
        t = todos[0]
        assert t["status"] == "X"
        assert t["completed"] is True

    def test_asterisk_bullet(self, client):
        todos = parse(client, "* [ ] Use asterisk bullet")
        assert len(todos) == 1
        assert todos[0]["status"] == " "
        assert todos[0]["completed"] is False


class TestAlternateCheckboxStyles:
    def test_forwarded(self, client):
        todos = parse(client, "- [>] Forwarded to next week")
        assert len(todos) == 1
        t = todos[0]
        assert t["status"] == ">"
        assert t["completed"] is False

    def test_scheduled(self, client):
        todos = parse(client, "- [<] Scheduled for review")
        assert len(todos) == 1
        t = todos[0]
        assert t["status"] == "<"
        assert t["completed"] is False

    def test_question(self, client):
        todos = parse(client, "- [?] Is this still needed?")
        assert len(todos) == 1
        t = todos[0]
        assert t["status"] == "?"
        assert t["completed"] is False

    def test_canceled(self, client):
        todos = parse(client, "- [-] Canceled task")
        assert len(todos) == 1
        t = todos[0]
        assert t["status"] == "-"
        assert t["completed"] is False

    def test_important(self, client):
        todos = parse(client, "- [!] Important reminder")
        assert len(todos) == 1
        t = todos[0]
        assert t["status"] == "!"
        assert t["completed"] is False

    def test_in_progress(self, client):
        todos = parse(client, "- [/] In progress")
        assert len(todos) == 1
        t = todos[0]
        assert t["status"] == "/"
        assert t["completed"] is False


class TestMultiLineContent:
    def test_mixed_styles_parsed_correctly(self, client):
        content = (
            "- [ ] Pending task\n"
            "- [x] Done task\n"
            "- [>] Forwarded task\n"
            "- [-] Canceled task\n"
            "- [?] Unclear task\n"
        )
        todos = parse(client, content)
        assert len(todos) == 5
        statuses = [t["status"] for t in todos]
        assert statuses == [" ", "x", ">", "-", "?"]

    def test_indented_subtask(self, client):
        content = "  - [ ] Subtask\n"
        todos = parse(client, content)
        assert len(todos) == 1
        assert todos[0]["indent_level"] == 2

    def test_non_checkbox_lines_ignored(self, client):
        content = (
            "# Heading\n"
            "Plain text line\n"
            "- [ ] Real todo\n"
            "- Not a checkbox\n"
        )
        todos = parse(client, content)
        assert len(todos) == 1
        assert todos[0]["content"] == "Real todo"

    def test_goal_lines_skipped(self, client):
        content = (
            "- [ ] Goal: Run a marathon\n"
            "- [ ] Buy milk\n"
        )
        todos = parse(client, content)
        assert len(todos) == 1
        assert todos[0]["content"] == "Buy milk"

    def test_line_numbers_are_one_indexed(self, client):
        content = "- [ ] First\n- [x] Second\n"
        todos = parse(client, content)
        assert todos[0]["line_number"] == 1
        assert todos[1]["line_number"] == 2

    def test_source_file_recorded(self, client):
        todos = client._parse_todos_from_content("- [ ] Task", "notes/daily.md")
        assert todos[0]["source_file"] == "notes/daily.md"


class TestTagAndPriorityExtraction:
    def test_tags_extracted(self, client):
        todos = parse(client, "- [ ] Review PR #123 #work #urgent")
        assert "work" in todos[0]["tags"]
        assert "urgent" in todos[0]["tags"]

    def test_high_priority_fire_emoji(self, client):
        todos = parse(client, "- [ ] 🔥 Critical bug fix")
        assert todos[0]["priority"] == "high"

    def test_no_priority(self, client):
        todos = parse(client, "- [ ] Low-stakes task")
        assert todos[0]["priority"] is None
