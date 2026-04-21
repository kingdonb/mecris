"""
ghost.headless_loopback — Headless subprocess wrapper for autonomous CLI turns.

Spawns ``gemini --yolo`` as a subprocess, pipes a prompt via stdin, captures
stdout/stderr, and enforces a hard timeout with SIGKILL to prevent runaway
token spend.

Usage::

    from ghost.headless_loopback import HeadlessLoopback

    wrapper = HeadlessLoopback()
    result = wrapper.run("Summarize today's activity goals")
    print(result.stdout)
    if result.timed_out:
        print("Process was killed due to timeout")

Environment::

    The command list defaults to ``["gemini", "--yolo"]``.  Override via the
    ``command`` constructor argument for testing or alternative CLIs.
"""

import logging
import os
import signal
import subprocess
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger("mecris.ghost.headless_loopback")

DEFAULT_TIMEOUT_SECONDS = 1800  # 30 minutes


@dataclass
class LoopbackResult:
    """Structured result of a headless subprocess execution.

    Attributes:
        exit_code: Process return code, or -1 if the process could not be
                   spawned.
        stdout:    Captured standard output (empty string if none).
        stderr:    Captured standard error (empty string if none).
        timed_out: True if the process was forcibly killed due to timeout.
        command:   The exact command list that was (or would have been) executed.
    """

    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    command: List[str] = field(default_factory=list)


class HeadlessLoopback:
    """Subprocess wrapper for headless ``gemini --yolo`` execution.

    Spawns the target command, pipes the prompt via stdin, captures
    stdout/stderr, and enforces a hard timeout with SIGKILL.  The child
    process runs in its own session (``start_new_session=True``) so that
    the kill signal targets only the child process tree.

    Always returns a :class:`LoopbackResult` — never raises.
    """

    DEFAULT_TIMEOUT: int = DEFAULT_TIMEOUT_SECONDS
    COMMAND: List[str] = ["gemini", "--yolo"]

    def __init__(
        self,
        command: Optional[List[str]] = None,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        log_output: bool = True,
    ) -> None:
        """
        Args:
            command:    Override the default ``gemini --yolo`` command list.
            timeout:    Maximum seconds before the subprocess is forcibly killed.
            log_output: If True, captured output is logged at DEBUG level.
        """
        self._command: List[str] = command if command is not None else list(self.COMMAND)
        self._timeout: int = timeout
        self._log_output: bool = log_output

    def run(self, prompt: str) -> LoopbackResult:
        """Spawn the subprocess, pipe *prompt* to stdin, and collect output.

        The subprocess is killed with SIGKILL if it does not complete within
        ``self._timeout`` seconds.  After a kill, :meth:`communicate` is
        called a second time to drain any remaining output.

        Args:
            prompt: Text written to the subprocess stdin.

        Returns:
            :class:`LoopbackResult` — never raises.
        """
        cmd = self._command
        logger.debug(
            "HeadlessLoopback: spawning %s (timeout=%ds)", cmd, self._timeout
        )

        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                # Isolate the child's process group so SIGKILL targets only
                # the child tree, not the parent process.
                start_new_session=True,
            )
        except FileNotFoundError:
            logger.error("HeadlessLoopback: command not found: %s", cmd[0])
            return LoopbackResult(
                exit_code=-1,
                stdout="",
                stderr=f"command not found: {cmd[0]}",
                timed_out=False,
                command=cmd,
            )
        except OSError as exc:
            logger.error("HeadlessLoopback: failed to spawn subprocess: %s", exc)
            return LoopbackResult(
                exit_code=-1,
                stdout="",
                stderr=str(exc),
                timed_out=False,
                command=cmd,
            )

        timed_out = False
        stdout: str = ""
        stderr: str = ""

        try:
            stdout, stderr = proc.communicate(input=prompt, timeout=self._timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            logger.warning(
                "HeadlessLoopback: timeout (%ds) reached — killing pid %d",
                self._timeout,
                proc.pid,
            )
            # Kill the entire process group to reap any children the CLI spawned.
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass  # Process already exited between timeout and kill attempt
            # Drain remaining output after kill.
            stdout, stderr = proc.communicate()

        exit_code = proc.returncode if proc.returncode is not None else -1

        if self._log_output:
            if stdout:
                logger.debug("HeadlessLoopback stdout:\n%s", stdout)
            if stderr:
                logger.debug("HeadlessLoopback stderr:\n%s", stderr)

        if timed_out:
            logger.warning(
                "HeadlessLoopback: process killed after timeout; exit_code=%d",
                exit_code,
            )
        else:
            logger.debug(
                "HeadlessLoopback: process exited; exit_code=%d", exit_code
            )

        return LoopbackResult(
            exit_code=exit_code,
            stdout=stdout or "",
            stderr=stderr or "",
            timed_out=timed_out,
            command=cmd,
        )
