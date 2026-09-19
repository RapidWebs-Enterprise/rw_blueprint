"""Deploy executor - executes deployment plans.

Transfers quadlet files and starts services via SSH.
Integrates with ImageLifecycle for image-aware deployments.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from rw_blueprint.deployer.lifecycle import ImageLifecycle
from rw_blueprint.deployer.plan import DeploymentAction, DeploymentPlan
from rw_blueprint.deployer.targets import RunResult, TargetManager
from rw_blueprint.schema import ImageRef


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
        self.lifecycle: ImageLifecycle | None = None
        self._image_cache: dict[str, ImageRef] = {}

    def set_image_lifecycle(self, lifecycle: ImageLifecycle) -> None:
        """Inject ImageLifecycle for image-aware deployments."""
        self.lifecycle = lifecycle

    def execute(self, plan: DeploymentPlan, node: str, output_dir: Path | None = None) -> DeploymentResult:
        """Execute deployment plan on target node.

        Args:
            plan: Deployment plan to execute.
            node: Target node identifier.
            output_dir: Directory containing generated quadlet artifacts.

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
                    self._deploy_service(node, action, output_dir=output_dir)
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

    def _ensure_image(self, node: str, service_id: str, image: str | None) -> ImageRef | None:
        """Ensure the required image exists on the target node.

        If the service has image_config, build/pull the image first.
        Returns the resolved ImageRef, or None if no image config.
        """
        if self.lifecycle is None or image is None:
            return None

        cache_key = f"{node}:{service_id}"
        if cache_key in self._image_cache:
            return self._image_cache[cache_key]

        # For now, just inspect the existing image
        image_ref = self.lifecycle.inspect(node, image)
        if image_ref:
            self._image_cache[cache_key] = image_ref
        return image_ref

    def _deploy_service(self, node: str, action: "DeploymentAction", output_dir: Path | None = None) -> None:
        """Deploy a single service."""
        # Check if service is already active
        check_result = self.target.execute(node, ["systemctl", "is-active", action.service])
        service_active = check_result.success and check_result.stdout.strip() == "active"

        # Also check if any container already using this port exists
        port_check = self.target.execute(node, ["podman", "ps", "-a", "--format", "{{.Ports}}"])
        port_exists = check_result.success and bool(port_check.stdout.strip())

        # Transfer quadlet file if provided
        if action.config_path and output_dir:
            local_path = output_dir / "quadlet" / f"{action.service}.container"
            if not local_path.exists():
                raise RuntimeError(f"Quadlet file not found: {local_path}")
            result = self.target.transfer_file(node, local_path, action.config_path, sudo=True)
            if not result.success:
                raise RuntimeError(f"Failed to transfer file: {result.stderr}")

            # Reload systemd if file was transferred
            result = self.target.execute(node, ["systemctl", "daemon-reload"], sudo=True)
            if not result.success:
                raise RuntimeError(f"Failed to reload systemd: {result.stderr}")

        # Only start if not already active and no port conflict
        if service_active or port_exists:
            return  # Already running

        result = self.target.execute(
            node,
            ["systemctl", "start", action.service],
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
