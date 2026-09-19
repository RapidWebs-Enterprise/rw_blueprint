"""Deployment state tracking.

Persists deployment history for rollback support.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class DeploymentRecord:
    """Record of a single deployment."""

    version: str
    deployed_at: str
    deployed_by: str
    status: str  # "healthy", "failed", "rolled_back"
    image: str
    config_hash: str
    #: Optional pinned image version (git SHA or semantic version).
    pinned_version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeploymentRecord":
        """Deserialize from dictionary."""
        return cls(**data)


class DeploymentState:
    """Track deployment history per service per node."""

    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _get_state_file(self, node: str, service: str) -> Path:
        """Get path to state file for a service."""
        return self.storage_dir / node / f"{service}.json"

    def record(self, node: str, service: str, record: DeploymentRecord) -> None:
        """Record a deployment.

        Args:
            node: Target node identifier.
            service: Service name.
            record: Deployment record to save.
        """
        state_file = self._get_state_file(node, service)
        state_file.parent.mkdir(parents=True, exist_ok=True)

        history = self.get_history(node, service)
        history.append(record.to_dict())

        state_file.write_text(json.dumps(history, indent=2))

    def get_history(self, node: str, service: str) -> list[dict[str, Any]]:
        """Get deployment history for a service.

        Args:
            node: Target node identifier.
            service: Service name.

        Returns:
            List of deployment records.
        """
        state_file = self._get_state_file(node, service)
        if not state_file.exists():
            return []

        return json.loads(state_file.read_text())

    def get_previous_healthy(self, node: str, service: str) -> DeploymentRecord | None:
        """Get the most recent healthy deployment.

        Args:
            node: Target node identifier.
            service: Service name.

        Returns:
            Previous healthy deployment record, or None if none exists.
        """
        history = self.get_history(node, service)
        for record_dict in reversed(history):
            record = DeploymentRecord.from_dict(record_dict)
            if record.status == "healthy":
                return record
        return None
