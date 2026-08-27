"""Canonical topology schema for rw_blueprint.

This module defines the Pydantic v2 models that constitute the single
objective source of truth for an infrastructure topology. The schema models
five entity types -- zones, nodes, services, links, and dependencies -- with
strict referential integrity enforced at parse time.

Design principles (grounded in the schema-design research report):

* ``id`` is the stable, unique key; ``name`` is display-only and may drift.
* Every reference (``node.zone``, ``node.host``, ``service.node``,
  ``link.from``/``link.to``, ``dependency.from``/``dependency.to``) must
  resolve to an entity that exists. Dangling references are rejected, never
  silently accepted -- this is the property that eliminates drift.
* External entities (e.g. ``cloudflare``, ``internet``) are modeled as nodes
  with ``type: external`` so that links remain strictly referential.
* The model is deterministic (stable field ordering, no ambient state) so an
  LLM agent can produce and reason about exact YAML diffs.
* ``schema_version`` is enforced: a document declaring an unsupported version
  is rejected, never silently accepted (the anti-drift property applied to the
  schema itself).
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "0.2"

NodeType = Literal["host", "container", "external", "device"]
ManagedBy = Literal["quadlet", "systemd", "host", "manual"]
ServiceKind = Literal[
    "application",
    "database",
    "proxy",
    "cache",
    "queue",
    "storage",
    "observability",
    "messaging",
    "dns",
    "web",
]
DependencyType = Literal["requires", "observes", "provides"]
Protocol = Literal["tcp", "udp"]


class _StrictModel(BaseModel):
    """Base model: forbid unknown fields so typos surface as errors, not drift."""

    model_config = ConfigDict(extra="forbid")


class Metadata(_StrictModel):
    """Top-level identifying information for a topology document."""

    name: str
    description: str = ""
    updated: date


class Zone(_StrictModel):
    """A trust/security boundary that groups nodes."""

    id: str
    name: str
    description: str = ""


class Node(_StrictModel):
    """A host, system container, external entity, or physical device."""

    id: str
    zone: str
    type: NodeType
    provider: str | None = None
    public_ip: str | None = None
    tailscale_ip: str | None = None
    #: Parent node id for containers (e.g. ``infra`` is hosted on ``srv1``).
    host: str | None = None
    #: Resource limits for container nodes (emitted into Incus profiles).
    cpu: int | None = None
    memory: str | None = None
    nic: str | None = None


class Port(_StrictModel):
    """A single service port with protocol and host-exposure semantics."""

    port: int
    #: Host port when published; defaults to ``port`` (1:1 mapping).
    public: int | None = None
    protocol: Protocol = "tcp"

    @property
    def host_port(self) -> int:
        """The host-side port, defaulting to the container port."""
        return self.public if self.public is not None else self.port


class Service(_StrictModel):
    """A running workload hosted on a node, exposing ports."""

    id: str
    node: str
    kind: ServiceKind
    #: Container image reference (emitted into quadlet units).
    image: str | None = None
    ports: list[Port] = Field(default_factory=list)
    managed_by: ManagedBy = "manual"


class Link(_StrictModel):
    """A connectivity edge between two nodes."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    from_: str = Field(alias="from")
    to: str
    protocol: str = "tcp"


class Dependency(_StrictModel):
    """A logical/operational edge between two services.

    Distinct from :class:`Link` (which is a network-connectivity edge between
    nodes). Dependencies drive startup ordering and blast-radius reasoning.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    from_: str = Field(alias="from")
    to: str
    type: DependencyType = "requires"


class Topology(BaseModel):
    """The root model: a complete, validated infrastructure topology."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    metadata: Metadata
    zones: list[Zone] = Field(default_factory=list)
    nodes: list[Node] = Field(default_factory=list)
    services: list[Service] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)
    dependencies: list[Dependency] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_schema_version(self) -> Topology:
        """Reject documents declaring an unsupported schema version."""
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"unsupported schema version '{self.schema_version}' "
                f"(supported: '{SCHEMA_VERSION}')"
            )
        return self

    @model_validator(mode="after")
    def _validate_references(self) -> Topology:
        """Enforce referential integrity and unique ids across the model."""
        zone_ids = {z.id for z in self.zones}
        node_ids = {n.id for n in self.nodes}
        service_ids = {s.id for s in self.services}

        self._check_unique([z.id for z in self.zones], "zone")
        self._check_unique([n.id for n in self.nodes], "node")
        self._check_unique([s.id for s in self.services], "service")
        self._check_unique([link.id for link in self.links], "link")
        self._check_unique([dep.id for dep in self.dependencies], "dependency")

        for node in self.nodes:
            if node.zone not in zone_ids:
                raise ValueError(f"node '{node.id}' references unknown zone '{node.zone}'")
            if node.host is not None and node.host not in node_ids:
                raise ValueError(f"node '{node.id}' references unknown host '{node.host}'")

        for service in self.services:
            if service.node not in node_ids:
                raise ValueError(f"service '{service.id}' references unknown node '{service.node}'")

        for link in self.links:
            if link.from_ not in node_ids:
                raise ValueError(f"link '{link.id}' references unknown node '{link.from_}'")
            if link.to not in node_ids:
                raise ValueError(f"link '{link.id}' references unknown node '{link.to}'")

        for dep in self.dependencies:
            if dep.from_ not in service_ids:
                raise ValueError(f"dependency '{dep.id}' references unknown service '{dep.from_}'")
            if dep.to not in service_ids:
                raise ValueError(f"dependency '{dep.id}' references unknown service '{dep.to}'")

        return self

    @staticmethod
    def _check_unique(ids: list[str], kind: str) -> None:
        seen: set[str] = set()
        for item_id in ids:
            if item_id in seen:
                raise ValueError(f"duplicate {kind} id '{item_id}'")
            seen.add(item_id)
