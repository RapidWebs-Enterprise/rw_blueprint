"""Generator-deployer integration.

Connects the generator's artifact output to the deployer's execution pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from rw_blueprint.generator import generate as generate_artifacts, load_topology
from rw_blueprint.schema import Topology


class ArtifactPath(Protocol):
    """Protocol for artifact paths."""

    name: str
    path: Path


@dataclass
class DeployableArtifact:
    """An artifact ready for deployment."""

    service_id: str
    node: str
    config_path: str  # Remote path on target node
    local_path: Path
    content: str


class GeneratorDeployerIntegration:
    """Bridge between generator and deployer components."""

    def __init__(self, topology: Topology, output_dir: Path | None = None):
        self.topology = topology
        self.output_dir = output_dir or Path("generated")

    def generate_for_node(self, node_id: str) -> list[DeployableArtifact]:
        """Generate deployable artifacts for a specific node.

        Args:
            node_id: Target node identifier.

        Returns:
            List of DeployableArtifact objects ready for transfer.
        """
        # Generate all artifacts first
        generated = generate_artifacts(self.topology, self.output_dir)

        # Filter for this node's services
        artifacts = []
        for service in self.topology.services:
            if service.node != node_id and service.managed_by == "quadlet":
                continue

            # Find the generated quadlet file
            quadlet_name = f"{service.id}.container"
            quadlet_path = self.output_dir / "quadlet" / quadlet_name

            if quadlet_path.exists():
                artifacts.append(
                    DeployableArtifact(
                        service_id=service.id,
                        node=node_id,
                        config_path=f"/etc/containers/systemd/{quadlet_name}",
                        local_path=quadlet_path,
                        content=quadlet_path.read_text(),
                    )
                )

        return artifacts

    def generate_all(self) -> dict[str, list[DeployableArtifact]]:
        """Generate deployable artifacts for all nodes.

        Returns:
            Dict mapping node_id to list of DeployableArtifact.
        """
        result = {}
        for node in self.topology.nodes:
            result[node.id] = self.generate_for_node(node.id)
        return result

    @classmethod
    def from_file(cls, topology_path: str | Path) -> GeneratorDeployerIntegration:
        """Create integration from a topology YAML file.

        Args:
            topology_path: Path to topology.yaml.

        Returns:
            Initialized GeneratorDeployerIntegration.
        """
        topology = load_topology(topology_path)
        return cls(topology)
