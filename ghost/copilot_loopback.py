"""
ghost.copilot_loopback — Headless subprocess wrapper for gh copilot CLI.

Wraps ``gh copilot -- -p "<prompt>"`` in non-interactive mode, capturing
stdout/stderr with configurable timeout enforcement via
:class:`~ghost.headless_loopback.HeadlessLoopback`.

Two convenience methods are provided:

- :meth:`CopilotLoopback.suggest` — ask copilot to suggest a shell command
- :meth:`CopilotLoopback.explain` — ask copilot to explain a shell command

Both return a :class:`~ghost.headless_loopback.LoopbackResult`.

Usage::

    from ghost.copilot_loopback import CopilotLoopback

    loopback = CopilotLoopback()

    result = loopback.suggest("list all running docker containers")
    print(result.stdout)

    result = loopback.explain("docker ps -a --format '{{.Names}}'")
    print(result.stdout)

Environment::

    ``gh`` must be available on PATH and authenticated (``gh auth login``).
    The ``-p`` flag requires gh copilot CLI ≥ 1.0 (installed by ``gh copilot``).
"""

import logging
from typing import List

from ghost.headless_loopback import HeadlessLoopback, LoopbackResult

logger = logging.getLogger("mecris.ghost.copilot_loopback")

DEFAULT_TIMEOUT_SECONDS = 120  # 2 minutes — copilot is much faster than gemini

# Base command: ``gh copilot --`` (the ``--`` prevents gh from consuming
# copilot-specific flags like ``-p``).
GH_COPILOT_BASE: List[str] = ["gh", "copilot", "--"]


class CopilotLoopback:
    """Subprocess wrapper for headless ``gh copilot`` execution.

    Wraps ``gh copilot -- -p "<prompt>"`` in non-interactive mode,
    capturing stdout/stderr with timeout enforcement via
    :class:`~ghost.headless_loopback.HeadlessLoopback`.

    Always returns a :class:`~ghost.headless_loopback.LoopbackResult` —
    never raises.
    """

    DEFAULT_TIMEOUT: int = DEFAULT_TIMEOUT_SECONDS

    def __init__(self, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> None:
        """
        Args:
            timeout: Maximum seconds before the subprocess is forcibly killed.
        """
        self._timeout = timeout

    def _run_prompt(self, prompt: str) -> LoopbackResult:
        """Build the gh copilot command with the prompt as a ``-p`` argument.

        The prompt is passed as a CLI argument (not via stdin) because
        ``gh copilot -p`` reads the prompt from the flag value, not from stdin.
        An empty string is piped to stdin to signal EOF immediately.

        Args:
            prompt: Full prompt text, including any preamble added by the
                    caller method (``suggest``/``explain``).

        Returns:
            :class:`~ghost.headless_loopback.LoopbackResult` — never raises.
        """
        cmd = GH_COPILOT_BASE + ["-p", prompt]
        logger.debug("CopilotLoopback: spawning %s (timeout=%ds)", cmd, self._timeout)
        loopback = HeadlessLoopback(command=cmd, timeout=self._timeout)
        # Pass empty stdin — gh copilot with -p reads from args, not stdin.
        return loopback.run("")

    def suggest(self, prompt: str) -> LoopbackResult:
        """Ask gh copilot to suggest a shell command for the given task.

        Prepends "Suggest a shell command to: " to the prompt so copilot
        understands the request type without requiring interactive subcommand
        selection.

        Args:
            prompt: Natural-language description of the shell task.

        Returns:
            :class:`~ghost.headless_loopback.LoopbackResult` with copilot's
            suggestion in ``stdout``.
        """
        full_prompt = f"Suggest a shell command to: {prompt}"
        logger.debug("CopilotLoopback.suggest: %r", full_prompt)
        return self._run_prompt(full_prompt)

    def explain(self, command: str) -> LoopbackResult:
        """Ask gh copilot to explain a shell command.

        Args:
            command: The shell command string to explain.

        Returns:
            :class:`~ghost.headless_loopback.LoopbackResult` with copilot's
            explanation in ``stdout``.
        """
        full_prompt = f"Explain this shell command: {command}"
        logger.debug("CopilotLoopback.explain: %r", full_prompt)
        return self._run_prompt(full_prompt)
