"""Tests for ServiceType extension in schema."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from rw_blueprint.schema import Service, Topology


def _base_topology() -> dict:
    """Return minimal valid topology base."""
    return {
        "schema_version": "0.2",
        "metadata": {
            "name": "test-topology",
            "updated": date(2026, 9, 15),
        },
        "zones": [{"id": "test", "name": "Test Zone"}],
        "nodes": [
            {"id": "node1", "zone": "test", "type": "host"},
        ],
        "services": [],
        "links": [],
        "dependencies": [],
    }


class TestServiceType:
    """Test ServiceType extension and Service model."""

    def test_service_default_service_type_is_container(self):
        """Service should default to container type for backward compatibility."""
        service = Service(
            id="caddy",
            node="node1",
            kind="proxy",
        )
        assert service.service_type == "container"

    def test_service_explicit_container_type(self):
        """Service should accept explicit container type."""
        service = Service(
            id="caddy",
            node="node1",
            kind="proxy",
            service_type="container",
        )
        assert service.service_type == "container"

    def test_service_explicit_systemd_type(self):
        """Service should accept explicit systemd type."""
        service = Service(
            id="knot-dns",
            node="node1",
            kind="dns",
            service_type="systemd",
        )
        assert service.service_type == "systemd"

    def test_service_systemd_can_be_privileged(self):
        """Systemd services can be privileged (root)."""
        service = Service(
            id="knot-dns",
            node="node1",
            kind="dns",
            service_type="systemd",
            privileged=True,
        )
        assert service.privileged is True

    def test_service_container_default_not_privileged(self):
        """Container services default to not privileged (rootless)."""
        service = Service(
            id="caddy",
            node="node1",
            kind="proxy",
            service_type="container",
        )
        assert service.privileged is False

    def test_topology_with_mixed_service_types(self):
        """Topology should support mixed container and systemd services."""
        topology_data = _base_topology()
        topology_data["services"] = [
            {
                "id": "caddy",
                "node": "node1",
                "kind": "proxy",
                "service_type": "container",
            },
            {
                "id": "knot-dns",
                "node": "node1",
                "kind": "dns",
                "service_type": "systemd",
                "privileged": True,
            },
        ]
        topology = Topology(**topology_data)
        assert len(topology.services) == 2
        assert topology.services[0].service_type == "container"
        assert topology.services[1].service_type == "systemd"

    def test_invalid_service_type_rejected(self):
        """Invalid service type should raise ValidationError."""
        with pytest.raises(ValidationError):
            Service(
                id="invalid",
                node="node1",
                kind="proxy",
                service_type="invalid_type",
            )
