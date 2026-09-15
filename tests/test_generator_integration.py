"""Tests for generator-deployer integration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from rw_blueprint.deployer.integration import DeployableArtifact, GeneratorDeployerIntegration
from rw_blueprint.schema import Topology, Node, Service, Zone, Metadata
from datetime import date


class TestDeployableArtifact:
    """Test DeployableArtifact dataclass."""

    def test_create_artifact(self):
        """Test creating a deployable artifact."""
        artifact = DeployableArtifact(
            service_id="caddy",
            node="infra",
            config_path="/etc/containers/systemd/caddy.container",
            local_path=Path("/tmp/caddy.container"),
            content="[Container]\nImage=localhost/caddy:latest\n",
        )
        assert artifact.service_id == "caddy"
        assert artifact.node == "infra"
        assert artifact.config_path == "/etc/containers/systemd/caddy.container"

    def test_artifact_repr(self):
        """Test artifact representation."""
        artifact = DeployableArtifact(
            service_id="caddy",
            node="infra",
            config_path="/etc/containers/systemd/caddy.container",
            local_path=Path("/tmp/caddy.container"),
            content="test",
        )
        assert "caddy" in repr(artifact)


class TestGeneratorDeployerIntegration:
    """Test GeneratorDeployerIntegration."""

    @patch("rw_blueprint.deployer.integration.generate_artifacts")
    def test_generate_for_node(self, mock_generate):
        """Test generating artifacts for a specific node."""
        # Setup mock
        mock_generate.return_value = [
            Path("/tmp/generated/quadlet/caddy.container"),
        ]

        topology = Topology(
            metadata=Metadata(name="test", updated=date.today()),
            zones=[Zone(id="mesh", name="Mesh")],
            nodes=[Node(id="infra", zone="mesh", type="host")],
            services=[
                Service(
                    id="caddy",
                    node="infra",
                    kind="proxy",
                    managed_by="quadlet",
                    image="localhost/caddy:latest",
                )
            ],
            links=[],
            dependencies=[],
        )

        integration = GeneratorDeployerIntegration(topology, Path("/tmp/generated"))

        # Create the quadlet file
        quadlet_dir = Path("/tmp/generated/quadlet")
        quadlet_dir.mkdir(parents=True, exist_ok=True)
        (quadlet_dir / "caddy.container").write_text("[Container]\nImage=localhost/caddy:latest\n")

        artifacts = integration.generate_for_node("infra")

        assert len(artifacts) == 1
        assert artifacts[0].service_id == "caddy"
        assert artifacts[0].node == "infra"
        assert artifacts[0].config_path == "/etc/containers/systemd/caddy.container"

    @patch("rw_blueprint.deployer.integration.generate_artifacts")
    def test_generate_all(self, mock_generate):
        """Test generating artifacts for all nodes."""
        mock_generate.return_value = []

        topology = Topology(
            metadata=Metadata(name="test", updated=date.today()),
            zones=[Zone(id="mesh", name="Mesh")],
            nodes=[
                Node(id="infra", zone="mesh", type="host"),
                Node(id="srv1", zone="mesh", type="host"),
            ],
            services=[
                Service(
                    id="caddy",
                    node="infra",
                    kind="proxy",
                    managed_by="quadlet",
                    image="localhost/caddy:latest",
                ),
                Service(
                    id="postfix",
                    node="srv1",
                    kind="messaging",
                    managed_by="quadlet",
                    image="localhost/postfix:latest",
                ),
            ],
            links=[],
            dependencies=[],
        )

        integration = GeneratorDeployerIntegration(topology, Path("/tmp/generated"))

        # Create quadlet files
        quadlet_dir = Path("/tmp/generated/quadlet")
        quadlet_dir.mkdir(parents=True, exist_ok=True)
        (quadlet_dir / "caddy.container").write_text("[Container]\nImage=localhost/caddy:latest\n")
        (quadlet_dir / "postfix.container").write_text("[Container]\nImage=localhost/postfix:latest\n")

        all_artifacts = integration.generate_all()

        assert "infra" in all_artifacts
        assert "srv1" in all_artifacts
        assert len(all_artifacts["infra"]) == 1
        assert len(all_artifacts["srv1"]) == 1
        assert all_artifacts["infra"][0].service_id == "caddy"
        assert all_artifacts["srv1"][0].service_id == "postfix"

    @patch("rw_blueprint.deployer.integration.load_topology")
    def test_from_file(self, mock_load):
        """Test loading from a topology file."""
        topology = Topology(
            metadata=Metadata(name="test", updated=date.today()),
            zones=[],
            nodes=[],
            services=[],
            links=[],
            dependencies=[],
        )
        mock_load.return_value = topology

        integration = GeneratorDeployerIntegration.from_file("/tmp/topology.yaml")

        assert integration.topology == topology
        assert integration.output_dir == Path("generated")
