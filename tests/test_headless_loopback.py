"""
Tests for ghost.headless_loopback.HeadlessLoopback.

Covers all four scenarios required by kingdonb#197:
  1. Output capture (stdout/stderr, exit code, prompt routing)
  2. Non-zero exit code propagated correctly
  3. Timeout enforcement (SIGKILL, timed_out flag, post-kill output drain)
  4. Subprocess spawn errors (command not found, OSError) — no raise
"""

import signal
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from ghost.headless_loopback import HeadlessLoopback, LoopbackResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_proc(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    """Build a minimal mock Popen object that behaves like a finished process."""
    proc = MagicMock()
    proc.returncode = returncode
    proc.pid = 12345
    proc.communicate.return_value = (stdout, stderr)
    return proc


# ---------------------------------------------------------------------------
# 1. Output capture
# ---------------------------------------------------------------------------


class TestOutputCapture:
    """HeadlessLoopback captures stdout/stderr and exit code correctly."""

    def test_happy_path_returns_stdout(self):
        proc = _make_proc(returncode=0, stdout="gemini says hello", stderr="")
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc):
            result = HeadlessLoopback().run("hello")
        assert result.stdout == "gemini says hello"
        assert result.stderr == ""
        assert result.exit_code == 0
        assert result.timed_out is False

    def test_stderr_captured(self):
        proc = _make_proc(returncode=0, stdout="", stderr="some warning")
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc):
            result = HeadlessLoopback().run("prompt")
        assert result.stderr == "some warning"

    def test_both_streams_captured(self):
        proc = _make_proc(returncode=0, stdout="output text", stderr="warning text")
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc):
            result = HeadlessLoopback().run("prompt")
        assert result.stdout == "output text"
        assert result.stderr == "warning text"

    def test_prompt_passed_to_communicate_as_input(self):
        proc = _make_proc(returncode=0)
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc):
            HeadlessLoopback().run("my prompt text")
        proc.communicate.assert_called_once_with(
            input="my prompt text", timeout=HeadlessLoopback.DEFAULT_TIMEOUT
        )

    def test_command_recorded_in_result(self):
        proc = _make_proc(returncode=0)
        custom_cmd = ["my-cli", "--flag"]
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc):
            result = HeadlessLoopback(command=custom_cmd).run("x")
        assert result.command == custom_cmd

    def test_default_command_is_gemini_yolo(self):
        proc = _make_proc(returncode=0)
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc) as mock_popen:
            HeadlessLoopback().run("prompt")
        call_args = mock_popen.call_args
        assert call_args[0][0] == ["gemini", "--yolo"]

    def test_result_type_is_loopback_result(self):
        proc = _make_proc(returncode=0)
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc):
            result = HeadlessLoopback().run("prompt")
        assert isinstance(result, LoopbackResult)

    def test_empty_output_returns_empty_strings(self):
        proc = _make_proc(returncode=0, stdout="", stderr="")
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc):
            result = HeadlessLoopback().run("prompt")
        assert result.stdout == ""
        assert result.stderr == ""


# ---------------------------------------------------------------------------
# 2. Non-zero exit codes
# ---------------------------------------------------------------------------


class TestNonZeroExitCode:
    """Non-zero and negative exit codes are propagated without raising."""

    def test_exit_code_1_propagated(self):
        proc = _make_proc(returncode=1, stdout="partial output", stderr="error detail")
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc):
            result = HeadlessLoopback().run("prompt")
        assert result.exit_code == 1
        assert result.timed_out is False
        assert result.stdout == "partial output"
        assert result.stderr == "error detail"

    def test_exit_code_2_propagated(self):
        proc = _make_proc(returncode=2)
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc):
            result = HeadlessLoopback().run("prompt")
        assert result.exit_code == 2

    def test_negative_exit_code_propagated(self):
        proc = _make_proc(returncode=-9)
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc):
            result = HeadlessLoopback().run("prompt")
        assert result.exit_code == -9

    def test_timed_out_false_on_non_zero_exit(self):
        proc = _make_proc(returncode=127)
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc):
            result = HeadlessLoopback().run("prompt")
        assert result.timed_out is False


# ---------------------------------------------------------------------------
# 3. Timeout enforcement
# ---------------------------------------------------------------------------


class TestTimeoutEnforcement:
    """Timeout fires SIGKILL, sets timed_out=True, and drains remaining output."""

    def _make_timeout_proc(
        self,
        post_kill_stdout: str = "",
        post_kill_stderr: str = "",
        timeout_seconds: int = 5,
        returncode: int = -9,
    ) -> MagicMock:
        """Build a Popen mock that raises TimeoutExpired on the first communicate call."""
        proc = MagicMock()
        proc.pid = 99
        proc.returncode = returncode
        proc.communicate.side_effect = [
            subprocess.TimeoutExpired(cmd="gemini", timeout=timeout_seconds),
            (post_kill_stdout, post_kill_stderr),
        ]
        return proc

    def test_timeout_sets_timed_out_flag(self):
        proc = self._make_timeout_proc()
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc), \
             patch("ghost.headless_loopback.os.killpg"), \
             patch("ghost.headless_loopback.os.getpgid", return_value=99):
            result = HeadlessLoopback(timeout=5).run("slow prompt")
        assert result.timed_out is True

    def test_process_killed_with_sigkill(self):
        proc = self._make_timeout_proc()
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc), \
             patch("ghost.headless_loopback.os.killpg") as mock_killpg, \
             patch("ghost.headless_loopback.os.getpgid", return_value=99):
            HeadlessLoopback(timeout=5).run("slow prompt")
        mock_killpg.assert_called_once_with(99, signal.SIGKILL)

    def test_output_drained_after_kill(self):
        proc = self._make_timeout_proc(
            post_kill_stdout="partial output", post_kill_stderr="stderr after kill"
        )
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc), \
             patch("ghost.headless_loopback.os.killpg"), \
             patch("ghost.headless_loopback.os.getpgid", return_value=99):
            result = HeadlessLoopback(timeout=5).run("slow prompt")
        assert result.stdout == "partial output"
        assert result.stderr == "stderr after kill"

    def test_exit_code_captured_after_kill(self):
        proc = self._make_timeout_proc(returncode=-9)
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc), \
             patch("ghost.headless_loopback.os.killpg"), \
             patch("ghost.headless_loopback.os.getpgid", return_value=99):
            result = HeadlessLoopback(timeout=5).run("slow prompt")
        assert result.exit_code == -9

    def test_process_lookup_error_on_kill_swallowed(self):
        """If the process dies just before SIGKILL, ProcessLookupError is suppressed."""
        proc = self._make_timeout_proc()
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc), \
             patch("ghost.headless_loopback.os.killpg", side_effect=ProcessLookupError), \
             patch("ghost.headless_loopback.os.getpgid", return_value=99):
            # Must not raise
            result = HeadlessLoopback(timeout=5).run("prompt")
        assert result.timed_out is True

    def test_custom_timeout_value_passed_to_communicate(self):
        proc = _make_proc(returncode=0)
        with patch("ghost.headless_loopback.subprocess.Popen", return_value=proc):
            HeadlessLoopback(timeout=120).run("prompt")
        proc.communicate.assert_called_once_with(input="prompt", timeout=120)


# ---------------------------------------------------------------------------
# 4. Subprocess spawn errors
# ---------------------------------------------------------------------------


class TestSubprocessErrors:
    """Spawn failures (FileNotFoundError, OSError) return a result without raising."""

    def test_file_not_found_returns_result(self):
        with patch("ghost.headless_loopback.subprocess.Popen", side_effect=FileNotFoundError):
            result = HeadlessLoopback().run("prompt")
        assert result.exit_code == -1
        assert result.timed_out is False
        assert "not found" in result.stderr
        assert result.stdout == ""

    def test_file_not_found_does_not_raise(self):
        with patch("ghost.headless_loopback.subprocess.Popen", side_effect=FileNotFoundError):
            # Must not raise
            HeadlessLoopback().run("prompt")

    def test_os_error_returns_result(self):
        with patch("ghost.headless_loopback.subprocess.Popen", side_effect=OSError("permission denied")):
            result = HeadlessLoopback().run("prompt")
        assert result.exit_code == -1
        assert "permission denied" in result.stderr

    def test_os_error_does_not_raise(self):
        with patch("ghost.headless_loopback.subprocess.Popen", side_effect=OSError("no such device")):
            # Must not raise
            HeadlessLoopback().run("prompt")

    def test_command_recorded_on_file_not_found(self):
        custom_cmd = ["no-such-binary", "--arg"]
        with patch("ghost.headless_loopback.subprocess.Popen", side_effect=FileNotFoundError):
            result = HeadlessLoopback(command=custom_cmd).run("prompt")
        assert result.command == custom_cmd

    def test_command_recorded_on_os_error(self):
        custom_cmd = ["restricted-bin"]
        with patch("ghost.headless_loopback.subprocess.Popen", side_effect=OSError("blocked")):
            result = HeadlessLoopback(command=custom_cmd).run("prompt")
        assert result.command == custom_cmd
