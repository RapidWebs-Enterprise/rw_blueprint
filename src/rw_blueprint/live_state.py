"""Live-state projection schema for rw_blueprint.

This module defines the Pydantic v2 models for the *observed* infrastructure
state. The live-state schema is a **projection** of the topology schema
(ADR-0007): it contains only the entities that can be directly observed by
probes (nodes, services, links). Zones and dependencies are design-time
constructs and are not observable at runtime.

Design principles:
* Every field mirrors the corresponding topology field exactly (same name,
  same type) so that diffing is mechanical and lossless.
* ``schema_version`` is enforced and must match the topology schema version.
* Probes emit fragments that conform to these models; the reconciler assembles
  them into a complete ``LiveState`` document.
* The models are deterministic and strictly validated (``extra="forbid"``).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rw_blueprint.schema import SCHEMA_VERSION, ManagedBy, Protocol, ServiceKind


class _StrictModel(BaseModel):
    """Base model: forbid unknown fields so typos surface as errors."""

    model_config = ConfigDict(extra="forbid")


class LiveMetadata(_StrictModel):
    """Metadata for a live-state snapshot."""

    captured_at: datetime
    captured_by: str = "rw_blueprint"
    schema_version: str = SCHEMA_VERSION


class LiveNode(_StrictModel):
    """An observed node (host, container, or external entity)."""

    id: str
    type: Literal["host", "container", "external", "device"]
    provider: str | None = None
    public_ip: str | None = None
    tailscale_ip: str | None = None
    host: str | None = None
    cpu: int | None = None
    memory: str | None = None
    state: Literal["running", "stopped", "frozen", "unknown"] = "unknown"


class LivePort(_StrictModel):
    """An observed service port."""

    port: int
    public: int | None = None
    protocol: Protocol = "tcp"

    @property
    def host_port(self) -> int:
        return self.public if self.public is not None else self.port


class LiveService(_StrictModel):
    """An observed running workload."""

    id: str
    node: str
    kind: ServiceKind
    image: str | None = None
    ports: list[LivePort] = Field(default_factory=list)
    managed_by: ManagedBy = "manual"
    state: Literal["running", "stopped", "paused", "unknown"] = "unknown"


class LiveLink(_StrictModel):
    """An observed connectivity edge between two nodes."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    from_: str = Field(alias="from")
    to: str
    protocol: str = "tcp"
    observed: bool = True


class LiveState(_StrictModel):
    """The root model: a complete, validated live-state snapshot."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    metadata: LiveMetadata
    nodes: list[LiveNode] = Field(default_factory=list)
    services: list[LiveService] = Field(default_factory=list)
    links: list[LiveLink] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_schema_version(self) -> LiveState:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"unsupported schema version '{self.schema_version}' "
                f"(supported: '{SCHEMA_VERSION}')"
            )
        return self

    @model_validator(mode="after")
    def _validate_references(self) -> LiveState:
        node_ids = {n.id for n in self.nodes}

        self._check_unique([n.id for n in self.nodes], "node")
        self._check_unique([s.id for s in self.services], "service")
        self._check_unique([link.id for link in self.links], "link")

        for service in self.services:
            if service.node not in node_ids:
                raise ValueError(f"service '{service.id}' references unknown node '{service.node}'")

        for link in self.links:
            if link.from_ not in node_ids:
                raise ValueError(f"link '{link.id}' references unknown node '{link.from_}'")
            if link.to not in node_ids:
                raise ValueError(f"link '{link.id}' references unknown node '{link.to}'")

        return self

    @staticmethod
    def _check_unique(ids: list[str], kind: str) -> None:
        seen: set[str] = set()
        for item_id in ids:
            if item_id in seen:
                raise ValueError(f"duplicate {kind} id '{item_id}'")
            seen.add(item_id)


class LiveStateFragment(_StrictModel):
    """A partial live-state fragment emitted by a single probe.

    Probes return fragments; the probe registry aggregates them into a
    complete LiveState. Fragments may be partial (e.g., only nodes, or
    only services) and are merged by the registry.
    """

    nodes: list[LiveNode] = Field(default_factory=list)
    services: list[LiveService] = Field(default_factory=list)
    links: list[LiveLink] = Field(default_factory=list)

    def merge(self, other: LiveStateFragment) -> LiveStateFragment:
        """Merge another fragment into this one (last-write-wins by id)."""
        node_map = {n.id: n for n in self.nodes}
        for n in other.nodes:
            node_map[n.id] = n

        service_map = {s.id: s for s in self.services}
        for s in other.services:
            service_map[s.id] = s

        link_map = {link.id: link for link in self.links}
        for other_link in other.links:
            link_map[other_link.id] = other_link

        return LiveStateFragment(
            nodes=list(node_map.values()),
            services=list(service_map.values()),
            links=list(link_map.values()),
        )
