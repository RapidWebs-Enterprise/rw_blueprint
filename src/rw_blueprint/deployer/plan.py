"""Deployment plan generation.

Compares desired state (topology services) with actual state (existing deployments)
to generate a deployment plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from typing import Protocol


class BlastRadius(Enum):
    """Blast radius of a deployment."""

    SERVICE = "service"      # Single service
    NODE = "node"           # Entire node
    ZONE = "zone"           # Service zone
    MESH = "mesh"           # All nodes


class DeploymentAction:
    """Single action in a deployment plan."""

    def __init__(
        self,
        node: str,
        service: str,
        action: str,
        config_path: str | None = None,
        dependencies: list[str] | None = None,
    ):
        self.node = node
        self.service = service
        self.action = action  # "create", "update", "delete"
        self.config_path = config_path
        self.dependencies = dependencies or []

    def __repr__(self) -> str:
        return f"DeploymentAction({self.node}/{self.service} {self.action})"


@dataclass
class DeploymentPlan:
    """Complete deployment plan."""

    actions: list[DeploymentAction]
    estimated_duration: timedelta
    blast_radius: BlastRadius
    requires_approval: bool = False

    @property
    def creates(self) -> list[DeploymentAction]:
        """Get create actions."""
        return [a for a in self.actions if a.action == "create"]

    @property
    def updates(self) -> list[DeploymentAction]:
        """Get update actions."""
        return [a for a in self.actions if a.action == "update"]

    @property
    def deletes(self) -> list[DeploymentAction]:
        """Get delete actions."""
        return [a for a in self.actions if a.action == "delete"]


class ServiceLike(Protocol):
    """Protocol for service objects."""

    id: str
    node: str
    kind: str
    image: str | None
    service_type: str
    privileged: bool


class PlanGenerator:
    """Generate deployment plans by comparing desired vs actual state."""

    def __init__(
        self,
        default_timeout: timedelta = timedelta(seconds=120),
        blast_radius: BlastRadius = BlastRadius.NODE,
    ):
        self.default_timeout = default_timeout
        self.blast_radius = blast_radius

    def generate(
        self,
        desired: list[ServiceLike],
        existing: dict[str, ServiceLike],
    ) -> DeploymentPlan:
        """Generate deployment plan.

        Args:
            desired: List of services from topology (desired state).
            existing: Map of existing service id to service (actual state).

        Returns:
            DeploymentPlan with actions to reconcile state.
        """
        actions: list[DeploymentAction] = []

        # Find creates and updates
        desired_ids = {s.id for s in desired}
        for service in desired:
            if service.id not in existing:
                # New service - create
                actions.append(DeploymentAction(
                    node=service.node,
                    service=service.id,
                    action="create",
                    config_path=f"/etc/containers/systemd/{service.id}.container",
                ))
            else:
                # Check if update needed (simplified: always update if exists)
                if self._needs_update(service, existing[service.id]):
                    actions.append(DeploymentAction(
                        node=service.node,
                        service=service.id,
                        action="update",
                        config_path=f"/etc/containers/systemd/{service.id}.container",
                    ))

        # Find deletes
        for sid, service in existing.items():
            if sid not in desired_ids:
                actions.append(DeploymentAction(
                    node=service.node,
                    service=sid,
                    action="delete",
                ))

        # Estimate duration (rough approximation)
        estimated_duration = self.default_timeout * len(actions)

        # Determine blast radius
        nodes_affected = {a.node for a in actions}
        if len(nodes_affected) > 1:
            blast_radius = BlastRadius.MESH
        elif any(a.action == "delete" for a in actions):
            blast_radius = BlastRadius.NODE
        else:
            blast_radius = BlastRadius.SERVICE

        return DeploymentPlan(
            actions=actions,
            estimated_duration=estimated_duration,
            blast_radius=blast_radius,
            requires_approval=blast_radius in (BlastRadius.ZONE, BlastRadius.MESH),
        )

    def _needs_update(self, desired: ServiceLike, existing: ServiceLike) -> bool:
        """Check if service needs update."""
        # Simplified: compare image and ports
        return (
            desired.image != existing.image
            or desired.privileged != existing.privileged
            or desired.service_type != existing.service_type
        )
