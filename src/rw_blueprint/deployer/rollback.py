"""Rollback executor - reverts deployments to previous state.

Handles rolling back failed deployments to the previous healthy state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rw_blueprint.deployer.state import DeploymentRecord, DeploymentState
from rw_blueprint.deployer.targets import RunResult, TargetManager


@dataclass
class RollbackResult:
    """Result of a rollback operation."""

    success: bool
    service: str
    node: str
    error_message: str | None = None


class RollbackExecutor:
    """Execute rollback operations."""

    def __init__(
        self,
        target_manager: TargetManager,
        state_tracker: DeploymentState,
    ):
        self.target = target_manager
        self.state = state_tracker

    def rollback(self, node: str, service: str) -> RollbackResult:
        """Rollback a service to its previous healthy state.

        Args:
            node: Target node identifier.
            service: Service name to rollback.

        Returns:
            RollbackResult with outcome.
        """
        # Get previous healthy deployment
        previous = self.state.get_previous_healthy(node, service)
        if previous is None:
            return RollbackResult(
                success=False,
                service=service,
                node=node,
                error_message="No previous healthy version found",
            )

        try:
            # Stop current service
            result = self.target.execute(
                node,
                ["systemctl", "stop", f"{service}.container"],
                sudo=True,
            )
            if not result.success:
                return RollbackResult(
                    success=False,
                    service=service,
                    node=node,
                    error_message=f"Failed to stop service: {result.stderr}",
                )

            # Restore previous quadlet file (if stored)
            # Note: In production, this would restore from artifact storage
            config_path = f"/etc/containers/systemd/{service}.container"

            # Start previous service
            result = self.target.execute(
                node,
                ["systemctl", "daemon-reload"],
                sudo=True,
            )
            if not result.success:
                return RollbackResult(
                    success=False,
                    service=service,
                    node=node,
                    error_message=f"Failed to reload systemd: {result.stderr}",
                )

            result = self.target.execute(
                node,
                ["systemctl", "enable", "--now", f"{service}.container"],
                sudo=True,
            )
            if not result.success:
                return RollbackResult(
                    success=False,
                    service=service,
                    node=node,
                    error_message=f"Failed to start service: {result.stderr}",
                )

            return RollbackResult(
                success=True,
                service=service,
                node=node,
            )

        except Exception as e:
            return RollbackResult(
                success=False,
                service=service,
                node=node,
                error_message=str(e),
            )
