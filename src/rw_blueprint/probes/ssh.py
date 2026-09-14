"""SSH remote command execution utilities."""

from __future__ import annotations

import logging
import subprocess
from typing import Tuple

_logger = logging.getLogger(__name__)


def run_remote_cmd(
    host: str,
    command: list[str],
    user: str = "sysop",
    timeout: int = 10,
) -> Tuple[int, str, str]:
    """Run a command on a remote host via SSH.

    Args:
        host: Remote hostname or IP
        command: Command to run
        user: SSH user
        timeout: Timeout in seconds

    Returns:
        Tuple of (exit_code, stdout, stderr)
    """
    ssh_cmd = ["ssh", f"{user}@{host}", *command]
    _logger.debug("Running remote command: %s", ssh_cmd)

    try:
        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"timeout after {timeout}s"
    except Exception as e:
        return -1, "", str(e)


def run_local_cmd(
    command: list[str],
    timeout: int = 10,
) -> Tuple[int, str, str]:
    """Run a command locally.

    Args:
        command: Command to run
        timeout: Timeout in seconds

    Returns:
        Tuple of (exit_code, stdout, stderr)
    """
    _logger.debug("Running local command: %s", command)

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"timeout after {timeout}s"
    except Exception as e:
        return -1, "", str(e)
