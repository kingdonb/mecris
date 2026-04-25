"""
Tests for ghost.copilot_loopback.CopilotLoopback.

Covers the deliverables required by kingdonb/mecris#206:
  1. Output capture (stdout/stderr, exit code)
  2. Command construction — verify gh copilot -- -p "<prompt>" is used
  3. Prompt prefixing — suggest/explain prepend the correct preamble
  4. Timeout enforcement (inherited from HeadlessLoopback via mock)
  5. Subprocess spawn errors — FileNotFoundError, OSError — no raise
"""

import signal
import subprocess
from unittest.mock import MagicMock, call, patch

import pytest

from ghost.copilot_loopback import CopilotLoopback, GH_COPILOT_BASE
from ghost.headless_loopback import LoopbackResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_proc(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    """Build a minimal mock Popen object that behaves like a finished process."""
    proc = MagicMock()
    proc.returncode = returncode
    proc.pid = 42
    proc.communicate.return_value = (stdout, stderr)
    return proc


# ---------------------------------------------------------------------------
# 1. Output capture
# ---------------------------------------------------------------------------


class TestOutputCapture:
    """CopilotLoopback.suggest / explain capture stdout/stderr and exit code."""

    def test_suggest_captures_stdout(self):
        proc = _make_proc(returncode=0, stdout="docker ps -a", stderr="")
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc):
            result = CopilotLoopback().suggest("list running docker containers")
        assert result.stdout == "docker ps -a"
        assert result.stderr == ""
        assert result.exit_code == 0
        assert result.timed_out is False

    def test_explain_captures_stdout(self):
        proc = _make_proc(returncode=0, stdout="Lists all processes", stderr="")
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc):
            result = CopilotLoopback().explain("ps aux")
        assert result.stdout == "Lists all processes"
        assert result.exit_code == 0

    def test_stderr_captured(self):
        proc = _make_proc(returncode=0, stdout="", stderr="auth warning")
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc):
            result = CopilotLoopback().suggest("something")
        assert result.stderr == "auth warning"

    def test_result_type_is_loopback_result(self):
        proc = _make_proc(returncode=0, stdout="ok", stderr="")
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc):
            result = CopilotLoopback().suggest("hello")
        assert isinstance(result, LoopbackResult)

    def test_empty_output_returns_empty_strings(self):
        proc = _make_proc(returncode=0, stdout="", stderr="")
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc):
            result = CopilotLoopback().suggest("anything")
        assert result.stdout == ""
        assert result.stderr == ""

    def test_non_zero_exit_propagated(self):
        proc = _make_proc(returncode=1, stdout="", stderr="error")
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc):
            result = CopilotLoopback().suggest("something")
        assert result.exit_code == 1
        assert result.timed_out is False


# ---------------------------------------------------------------------------
# 2. Command construction
# ---------------------------------------------------------------------------


class TestCommandConstruction:
    """CopilotLoopback builds the correct gh copilot -- -p <prompt> command."""

    def test_suggest_uses_gh_copilot_base(self):
        proc = _make_proc()
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc) as mock_popen:
            CopilotLoopback().suggest("list files")
        cmd = mock_popen.call_args[0][0]
        assert cmd[:3] == ["gh", "copilot", "--"]

    def test_suggest_passes_p_flag(self):
        proc = _make_proc()
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc) as mock_popen:
            CopilotLoopback().suggest("list files")
        cmd = mock_popen.call_args[0][0]
        assert "-p" in cmd

    def test_explain_uses_gh_copilot_base(self):
        proc = _make_proc()
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc) as mock_popen:
            CopilotLoopback().explain("ls -la")
        cmd = mock_popen.call_args[0][0]
        assert cmd[:3] == ["gh", "copilot", "--"]

    def test_command_recorded_in_result(self):
        proc = _make_proc()
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc):
            result = CopilotLoopback().suggest("test")
        assert result.command[:3] == ["gh", "copilot", "--"]
        assert "-p" in result.command

    def test_gh_copilot_base_constant(self):
        assert GH_COPILOT_BASE == ["gh", "copilot", "--"]


# ---------------------------------------------------------------------------
# 3. Prompt prefixing
# ---------------------------------------------------------------------------


class TestPromptPrefixing:
    """suggest and explain prepend the correct preamble to the user's text."""

    def test_suggest_prepends_suggest_preamble(self):
        proc = _make_proc()
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc) as mock_popen:
            CopilotLoopback().suggest("delete all tmp files")
        cmd = mock_popen.call_args[0][0]
        # The last element is the full prompt passed via -p
        full_prompt = cmd[cmd.index("-p") + 1]
        assert "Suggest a shell command" in full_prompt
        assert "delete all tmp files" in full_prompt

    def test_explain_prepends_explain_preamble(self):
        proc = _make_proc()
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc) as mock_popen:
            CopilotLoopback().explain("find . -name '*.pyc' -delete")
        cmd = mock_popen.call_args[0][0]
        full_prompt = cmd[cmd.index("-p") + 1]
        assert "Explain" in full_prompt
        assert "find . -name '*.pyc' -delete" in full_prompt

    def test_suggest_empty_prompt_still_prefixed(self):
        proc = _make_proc()
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc) as mock_popen:
            CopilotLoopback().suggest("")
        cmd = mock_popen.call_args[0][0]
        full_prompt = cmd[cmd.index("-p") + 1]
        assert "Suggest a shell command" in full_prompt


# ---------------------------------------------------------------------------
# 4. Timeout enforcement
# ---------------------------------------------------------------------------


class TestTimeoutEnforcement:
    """Timeout is forwarded to HeadlessLoopback and causes timed_out=True."""

    def _make_timeout_proc(self, returncode: int = -9) -> MagicMock:
        proc = MagicMock()
        proc.pid = 99
        proc.returncode = returncode
        proc.communicate.side_effect = [
            subprocess.TimeoutExpired(cmd="gh", timeout=30),
            ("", ""),
        ]
        return proc

    def test_suggest_timeout_sets_timed_out_flag(self):
        proc = self._make_timeout_proc()
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc), \
             patch("ghost.headless_loopback.os.killpg"), \
             patch("ghost.headless_loopback.os.getpgid", return_value=99):
            result = CopilotLoopback(timeout=30).suggest("slow task")
        assert result.timed_out is True

    def test_explain_timeout_sets_timed_out_flag(self):
        proc = self._make_timeout_proc()
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc), \
             patch("ghost.headless_loopback.os.killpg"), \
             patch("ghost.headless_loopback.os.getpgid", return_value=99):
            result = CopilotLoopback(timeout=30).explain("slow command")
        assert result.timed_out is True

    def test_custom_timeout_propagated(self):
        proc = _make_proc(returncode=0)
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc):
            CopilotLoopback(timeout=45).suggest("check timeout")
        proc.communicate.assert_called_once_with(input="", timeout=45)


# ---------------------------------------------------------------------------
# 5. Subprocess spawn errors
# ---------------------------------------------------------------------------


class TestSpawnErrors:
    """FileNotFoundError and OSError return a LoopbackResult without raising."""

    def test_file_not_found_returns_result(self):
        with patch("ghost.headless_loopback.subprocess.Popen", side_effect=FileNotFoundError):
            result = CopilotLoopback().suggest("test")
        assert result.exit_code == -1
        assert result.timed_out is False
        assert result.stdout == ""

    def test_file_not_found_does_not_raise(self):
        with patch("ghost.headless_loopback.subprocess.Popen", side_effect=FileNotFoundError):
            CopilotLoopback().suggest("test")  # must not raise

    def test_os_error_returns_result(self):
        with patch("ghost.headless_loopback.subprocess.Popen", side_effect=OSError("blocked")):
            result = CopilotLoopback().explain("ls")
        assert result.exit_code == -1
        assert "blocked" in result.stderr

    def test_os_error_does_not_raise(self):
        with patch("ghost.headless_loopback.subprocess.Popen", side_effect=OSError("no device")):
            CopilotLoopback().explain("ls")  # must not raise
