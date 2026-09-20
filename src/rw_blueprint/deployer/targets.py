"""Target manager for SSH connections.

Manages SSH connections to remote nodes for deployment execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from subprocess import run, PIPE, CalledProcessError
import shlex


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
            sudo: Whether to prepend sudo (uses -n for non-interactive).

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

        # Build SSH command - use list form to prevent shell injection
        ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=10"]
        if key:
            ssh_cmd.extend(["-i", key])
        ssh_cmd.extend([f"{user}@{host}"])

        # Prepend sudo if needed (use -n for non-interactive)
        if sudo:
            full_cmd = ["sudo", "-n"] + command
        else:
            full_cmd = command

        # Execute via SSH using list form (no bash -c)
        try:
            result = run(
                ssh_cmd + full_cmd,
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
        sudo: bool = False,
    ) -> RunResult:
        """Transfer file to remote node via SCP.

        Args:
            node_id: Target node identifier.
            local_path: Local file path.
            remote_path: Remote file path.
            sudo: Whether to use sudo for the transfer.

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

        # For system directories, use sudo via tee
        if sudo:
            # Transfer to temp location first, then move with sudo
            tmp_path = f"/tmp/{Path(remote_path).name}"
            scp_cmd = [
                "scp",
                "-o", "StrictHostKeyChecking=no",
                "-o", "ConnectTimeout=10",
                str(local_path),
                f"{user}@{host}:{tmp_path}",
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
                # Move to final location with sudo
                # Use single SSH call with sudo (not double sudo)
                move_result = self.execute(node_id, ["mv", tmp_path, str(remote_path)], sudo=True)
                return move_result
            except FileNotFoundError:
                return RunResult(
                    success=False,
                    returncode=-1,
                    stdout="",
                    stderr="SCP command not found",
                )

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
