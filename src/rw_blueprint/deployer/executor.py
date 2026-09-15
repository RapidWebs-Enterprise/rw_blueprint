"""Deploy executor - executes deployment plans.

Transfers quadlet files and starts services via SSH.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from rw_blueprint.deployer.plan import DeploymentAction, DeploymentPlan
from rw_blueprint.deployer.targets import RunResult, TargetManager


class ServiceLike(Protocol):
    """Protocol for service objects."""

    id: str
    node: str
    image: str | None


@dataclass
class DeploymentResult:
    """Result of a deployment execution."""

    success: bool
    node: str
    actions_completed: list[str]
    error_message: str | None = None


class DeployExecutor:
    """Execute deployment plans on target nodes."""

    def __init__(self, target_manager: TargetManager):
        self.target = target_manager

    def execute(self, plan: DeploymentPlan, node: str) -> DeploymentResult:
        """Execute deployment plan on target node.

        Args:
            plan: Deployment plan to execute.
            node: Target node identifier.

        Returns:
            DeploymentResult with execution details.
        """
        actions_completed: list[str] = []
        errors: list[str] = []

        for action in plan.actions:
            if action.node != node:
                continue

            try:
                if action.action == "create" or action.action == "update":
                    self._deploy_service(node, action)
                    actions_completed.append(action.service)
                elif action.action == "delete":
                    self._undeploy_service(node, action)
                    actions_completed.append(action.service)
            except Exception as e:
                errors.append(f"{action.service}: {e}")

        success = len(errors) == 0
        error_message = "; ".join(errors) if errors else None

        return DeploymentResult(
            success=success,
            node=node,
            actions_completed=actions_completed,
            error_message=error_message,
        )

    def _deploy_service(self, node: str, action: "DeploymentAction") -> None:
        """Deploy a single service."""
        # Transfer quadlet file
        if action.config_path:
            result = self.target.transfer_file(node, action.config_path, action.config_path)
            if not result.success:
                raise RuntimeError(f"Failed to transfer file: {result.stderr}")

        # Reload systemd and start service
        result = self.target.execute(node, ["systemctl", "daemon-reload"], sudo=True)
        if not result.success:
            raise RuntimeError(f"Failed to reload systemd: {result.stderr}")

        result = self.target.execute(
            node,
            ["systemctl", "enable", "--now", f"{action.service}.container"],
            sudo=True,
        )
        if not result.success:
            raise RuntimeError(f"Failed to start service: {result.stderr}")

    def _undeploy_service(self, node: str, action: "DeploymentAction") -> None:
        """Undeploy a single service."""
        result = self.target.execute(
            node,
            ["systemctl", "stop", f"{action.service}.container"],
            sudo=True,
        )
        if not result.success:
            raise RuntimeError(f"Failed to stop service: {result.stderr}")

        result = self.target.execute(
            node,
            ["systemctl", "disable", f"{action.service}.container"],
            sudo=True,
        )
        if not result.success:
            raise RuntimeError(f"Failed to disable service: {result.stderr}")

        # Remove quadlet file
        if action.config_path:
            result = self.target.execute(
                node, ["rm", "-f", action.config_path], sudo=True
            )
            if not result.success:
                raise RuntimeError(f"Failed to remove config: {result.stderr}")

        # Reload systemd
        result = self.target.execute(node, ["systemctl", "daemon-reload"], sudo=True)
        if not result.success:
            raise RuntimeError(f"Failed to reload systemd: {result.stderr}")
