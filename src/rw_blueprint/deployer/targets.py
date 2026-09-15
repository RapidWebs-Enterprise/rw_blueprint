"""Target manager for SSH connections.

Manages SSH connections to remote nodes for deployment execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from subprocess import run, PIPE, CalledProcessError


@dataclass
class RunResult:
    """Result of a remote command execution."""

    success: bool
    returncode: int
    stdout: str
    stderr: str


class TargetManager:
    """Manage SSH connections to target nodes."""

    def __init__(self, nodes: dict[str, dict]):
        """Initialize target manager.

        Args:
            nodes: Dict mapping node_id to connection config.
                  Example: {"infra": {"host": "100.79.58.118", "user": "sysop"}}
        """
        self.nodes = nodes

    def execute(
        self,
        node_id: str,
        command: list[str],
        timeout: int = 30,
        sudo: bool = False,
    ) -> RunResult:
        """Execute command on remote node via SSH.

        Args:
            node_id: Target node identifier.
            command: Command to execute.
            timeout: Timeout in seconds.
            sudo: Whether to prepend sudo.

        Returns:
            RunResult with execution details.
        """
        if node_id not in self.nodes:
            return RunResult(
                success=False,
                returncode=-1,
                stdout="",
                stderr=f"Unknown node: {node_id}",
            )

        node_config = self.nodes[node_id]
        host = node_config.get("host", node_id)
        user = node_config.get("user", "sysop")
        key = node_config.get("key")

        # Build SSH command
        ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10"]
        if key:
            ssh_cmd.extend(["-i", key])
        ssh_cmd.extend([f"{user}@{host}"])

        # Prepend sudo if needed
        if sudo:
            full_cmd = ["sudo"] + command
        else:
            full_cmd = command

        # Execute via SSH
        try:
            result = run(
                ["bash", "-c", f"{' '.join(ssh_cmd)} {' '.join(full_cmd)}"],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return RunResult(
                success=result.returncode == 0,
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        except FileNotFoundError:
            return RunResult(
                success=False,
                returncode=-1,
                stdout="",
                stderr="SSH command not found",
            )
        except KeyboardInterrupt:
            return RunResult(
                success=False,
                returncode=-1,
                stdout="",
                stderr="Interrupted",
            )

    def transfer_file(
        self,
        node_id: str,
        local_path: str | Path,
        remote_path: str | Path,
    ) -> RunResult:
        """Transfer file to remote node via SCP.

        Args:
            node_id: Target node identifier.
            local_path: Local file path.
            remote_path: Remote file path.

        Returns:
            RunResult with transfer details.
        """
        if node_id not in self.nodes:
            return RunResult(
                success=False,
                returncode=-1,
                stdout="",
                stderr=f"Unknown node: {node_id}",
            )

        node_config = self.nodes[node_id]
        host = node_config.get("host", node_id)
        user = node_config.get("user", "sysop")

        scp_cmd = [
            "scp",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=10",
            str(local_path),
            f"{user}@{host}:{remote_path}",
        ]

        try:
            result = run(scp_cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                return RunResult(
                    success=False,
                    returncode=result.returncode,
                    stdout="",
                    stderr=result.stderr,
                )
            return RunResult(success=True, returncode=0, stdout="", stderr="")
        except FileNotFoundError:
            return RunResult(
                success=False,
                returncode=-1,
                stdout="",
                stderr="SCP command not found",
            )

    def ensure_directory(self, node_id: str, path: str) -> RunResult:
        """Ensure directory exists on remote node.

        Args:
            node_id: Target node identifier.
            path: Directory path to create.

        Returns:
            RunResult with execution details.
        """
        return self.execute(node_id, ["mkdir", "-p", path], sudo=True)
