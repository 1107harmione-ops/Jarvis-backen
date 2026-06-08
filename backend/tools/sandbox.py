import asyncio
import shlex
from typing import Optional
from backend.core.logging import get_logger

logger = get_logger(__name__)

# Whitelist of allowed commands (no arbitrary shell access).
ALLOWED_COMMANDS: frozenset[str] = frozenset({
    "date", "uptime", "uname", "whoami",
    "ls", "pwd", "echo", "cat", "head", "tail", "wc",
    "python3", "python",
})

# Argument / command-string patterns that are always blocked.
BLOCKED_PATTERNS: tuple[str, ...] = (
    "..", ";/", "|", "&&", "||", "`", "$(",
    ">", "<", "&>", "2>",
)


class SandboxedExecutor:
    """Execute shell commands in a restricted sandbox.

    The sandbox enforces two layers of defence:

    1. **Command whitelist** — only executables in
       :data:`ALLOWED_COMMANDS` may be invoked.
    2. **Pattern blocking** — common injection / path-traversal
       sequences are rejected before the process is spawned.

    All executions are subject to a configurable timeout and an output
    byte cap to prevent runaway processes from consuming resources.
    """

    # ── Validation ─────────────────────────────────────────────────

    @staticmethod
    def validate_command(command: str) -> tuple[bool, str]:
        """Check whether *command* is permitted by sandbox rules.

        Returns
        -------
        (is_valid, reason)
            ``is_valid`` is ``True`` when the command may proceed;
            ``reason`` is an empty string in that case, otherwise a
            human-readable explanation.
        """
        parts = shlex.split(command)
        if not parts:
            return False, "Empty command"

        cmd = parts[0]

        # Base command must be in the whitelist.
        if cmd not in ALLOWED_COMMANDS:
            return False, f"Command '{cmd}' is not in the whitelist"

        # Reject known dangerous / injection patterns anywhere in the string.
        for pattern in BLOCKED_PATTERNS:
            if pattern in command:
                return False, f"Command contains blocked pattern: {pattern}"

        return True, ""

    # ── Execution ──────────────────────────────────────────────────

    @staticmethod
    async def execute(
        command: str,
        timeout: int = 10,
        max_output: int = 1024 * 100,  # 100 KB
    ) -> dict:
        """Run *command* inside the sandbox.

        Parameters
        ----------
        command : str
            Shell command to execute.  Must pass :meth:`validate_command`.
        timeout : int
            Maximum wall-clock seconds before the process is killed.
        max_output : int
            Maximum bytes captured from stdout **and** stderr individually.

        Returns
        -------
        dict
            ``{"success": bool, "returncode": int | None,
            "stdout": str, "stderr": str, "error": str}``
        """
        is_valid, reason = SandboxedExecutor.validate_command(command)
        if not is_valid:
            return {"success": False, "error": reason, "stdout": "", "stderr": ""}

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=max_output,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                return {
                    "success": False,
                    "error": f"Command timed out after {timeout}s",
                    "stdout": "",
                    "stderr": "",
                }

            stdout_str = stdout.decode("utf-8", errors="replace")[:max_output]
            stderr_str = stderr.decode("utf-8", errors="replace")[:max_output]

            return {
                "success": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": stdout_str,
                "stderr": stderr_str,
                "error": stderr_str if proc.returncode != 0 else "",
            }

        except FileNotFoundError:
            return {
                "success": False,
                "error": f"Command not found: {command}",
                "stdout": "",
                "stderr": "",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "stdout": "",
                "stderr": "",
            }
