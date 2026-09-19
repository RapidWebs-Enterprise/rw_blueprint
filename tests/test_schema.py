"""Tests for the canonical topology schema."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from rw_blueprint.schema import Topology


def _valid_topology() -> dict:
    """Return a minimal, fully-valid topology document."""
    return {
        "schema_version": "0.2",
        "metadata": {
            "name": "rapidwebs-rwdn",
            "description": "RapidWebs Distributed Network",
            "updated": date(2026, 8, 27),
        },
        "zones": [
            {"id": "edge", "name": "Edge"},
            {"id": "infra", "name": "Infra"},
        ],
        "nodes": [
            {
                "id": "cloudflare",
                "zone": "edge",
                "type": "external",
            },
            {
                "id": "srv1",
                "zone": "edge",
                "type": "host",
                "provider": "hetzner",
                "public_ip": "89.167.54.98",
                "tailscale_ip": "100.64.94.58",
            },
            {
                "id": "infra",
                "zone": "infra",
                "type": "container",
                "host": "srv1",
                "tailscale_ip": "100.64.255.48",
                "cpu": 2,
                "memory": "2GiB",
            },
        ],
        "services": [
            {
                "id": "pgvector",
                "node": "infra",
                "kind": "database",
                "image": "docker.io/pgvector/pgvector:pg16",
                "ports": [{"port": 5432}],
                "managed_by": "quadlet",
            },
            {
                "id": "honcho",
                "node": "infra",
                "kind": "application",
                "image": "docker.io/rapidwebs/honcho:latest",
                "ports": [{"port": 8000}],
                "managed_by": "quadlet",
            },
        ],
        "dependencies": [
            {
                "id": "honcho-requires-pgvector",
                "from": "honcho",
                "to": "pgvector",
                "type": "requires",
            },
        ],
        "links": [
            {
                "id": "cloudflare-to-srv1",
                "from": "cloudflare",
                "to": "srv1",
                "protocol": "https",
            },
        ],
    }


def test_valid_topology_parses() -> None:
    """A fully-valid document parses without error."""
    topology = Topology.model_validate(_valid_topology())
    assert topology.metadata.name == "rapidwebs-rwdn"
    assert len(topology.nodes) == 3
    assert len(topology.services) == 2
    assert len(topology.dependencies) == 1


def test_duplicate_node_id_rejected() -> None:
    """Duplicate ids within an entity type are rejected."""
    data = _valid_topology()
    data["nodes"].append({"id": "srv1", "zone": "edge", "type": "host"})
    with pytest.raises(ValidationError, match="duplicate node id 'srv1'"):
        Topology.model_validate(data)


def test_duplicate_dependency_id_rejected() -> None:
    """Duplicate dependency ids are rejected."""
    data = _valid_topology()
    data["dependencies"].append(
        {"id": "honcho-requires-pgvector", "from": "honcho", "to": "pgvector"}
    )
    with pytest.raises(ValidationError, match="duplicate dependency id"):
        Topology.model_validate(data)


def test_dangling_zone_reference_rejected() -> None:
    """A node referencing a non-existent zone is rejected."""
    data = _valid_topology()
    data["nodes"].append({"id": "ghost", "zone": "nowhere", "type": "host"})
    with pytest.raises(ValidationError, match="unknown zone 'nowhere'"):
        Topology.model_validate(data)


def test_dangling_host_reference_rejected() -> None:
    """A container referencing a non-existent host is rejected."""
    data = _valid_topology()
    data["nodes"].append({"id": "orphan", "zone": "infra", "type": "container", "host": "missing"})
    with pytest.raises(ValidationError, match="unknown host 'missing'"):
        Topology.model_validate(data)


def test_dangling_service_node_rejected() -> None:
    """A service referencing a non-existent node is rejected."""
    data = _valid_topology()
    data["services"].append({"id": "ghost-svc", "node": "missing", "kind": "application"})
    with pytest.raises(ValidationError, match="unknown node 'missing'"):
        Topology.model_validate(data)


def test_dangling_dependency_rejected() -> None:
    """A dependency referencing a non-existent service is rejected."""
    data = _valid_topology()
    data["dependencies"].append(
        {"id": "bad-dep", "from": "honcho", "to": "missing", "type": "requires"}
    )
    with pytest.raises(ValidationError, match="unknown service 'missing'"):
        Topology.model_validate(data)


def test_dangling_link_reference_rejected() -> None:
    """A link referencing a non-existent node is rejected."""
    data = _valid_topology()
    data["links"].append({"id": "bad-link", "from": "srv1", "to": "missing"})
    with pytest.raises(ValidationError, match="unknown node 'missing'"):
        Topology.model_validate(data)


def test_unknown_field_rejected() -> None:
    """Extra fields are forbidden (strict schema)."""
    data = _valid_topology()
    data["nodes"][1]["bogus_field"] = True
    with pytest.raises(ValidationError):
        Topology.model_validate(data)


def test_unsupported_schema_version_rejected() -> None:
    """A document declaring an unsupported schema version is rejected."""
    data = _valid_topology()
    data["schema_version"] = "9.9"
    with pytest.raises(ValidationError, match="unsupported schema version '9.9'"):
        Topology.model_validate(data)


def test_invalid_kind_rejected() -> None:
    """A service with an unknown kind is rejected."""
    data = _valid_topology()
    data["services"][0]["kind"] = "not-a-real-kind"
    with pytest.raises(ValidationError):
        Topology.model_validate(data)


def test_link_from_alias_round_trips() -> None:
    """The ``from`` alias serializes back to the ``from`` key."""
    topology = Topology.model_validate(_valid_topology())
    dumped = topology.model_dump(by_alias=True)
    assert dumped["links"][0]["from"] == "cloudflare"


def test_round_trip_lossless() -> None:
    """parse -> dump -> parse is lossless (DOC-001)."""
    topology = Topology.model_validate(_valid_topology())
    dumped = topology.model_dump(by_alias=True, mode="json")
    reparsed = Topology.model_validate(dumped)
    assert reparsed == topology


def test_structured_port_defaults() -> None:
    """A port with only ``port`` set defaults public=port, protocol=tcp."""
    topology = Topology.model_validate(_valid_topology())
    port = topology.services[0].ports[0]
    assert port.port == 5432
    assert port.host_port == 5432
    assert port.protocol == "tcp"


def test_service_with_image_config() -> None:
    """A service can optionally have image_config."""
    data = _valid_topology()
    data["services"][0]["image_config"] = {
        "build_context": "/home/sysop/honcho",
        "tag_strategy": "git-sha",
        "labels": {"org.git.sha": "abc123"},
    }
    topology = Topology.model_validate(data)
    svc = topology.services[0]
    assert svc.image_config is not None
    assert svc.image_config.build_context == "/home/sysop/honcho"
    assert svc.image_config.tag_strategy == "git-sha"
    assert svc.image_config.labels["org.git.sha"] == "abc123"


def test_service_without_image_config() -> None:
    """Services without image_config remain backward compatible."""
    topology = Topology.model_validate(_valid_topology())
    assert topology.services[0].image_config is None


def test_image_config_forbids_unknown_fields() -> None:
    """Unknown fields in image_config are rejected."""
    data = _valid_topology()
    data["services"][0]["image_config"] = {"bogus_field": True}
    with pytest.raises(ValidationError):
        Topology.model_validate(data)


def test_image_ref_reference_property() -> None:
    """ImageRef.reference formats correctly with and without digest."""
    from rw_blueprint.schema import ImageRef

    ref = ImageRef(name="honcho", tag="v1.0", source="build")
    assert ref.reference == "honcho:v1.0"

    ref_with_digest = ImageRef(name="honcho", tag="v1.0", digest="sha256:abc123")
    assert ref_with_digest.reference == "honcho:v1.0@sha256:abc123"


def test_image_ref_default_source() -> None:
    """ImageRef defaults source to 'pull'."""
    from rw_blueprint.schema import ImageRef

    ref = ImageRef(name="honcho", tag="latest")
    assert ref.source == "pull"
