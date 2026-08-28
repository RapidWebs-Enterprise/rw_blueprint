"""Remediation proposal engine (ADR-0015).

Generates structured, gated remediation proposals from drift reports.
Each proposal is a minimal JSON Patch (RFC 6902) operation with a blast-radius
estimate and severity classification. Proposals are NEVER auto-applied — they
are gated behind human (or agent-with-HITL) approval.

Design principles:
* One proposal per drift item (atomic, reversible).
* Blast radius is estimated from entity type and operation scope.
* Proposals are serializable to JSON for agent consumption.
* The ``apply`` method exists for programmatic use but is always gated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from rw_blueprint.reconciler import DriftCategory, DriftItem, DriftReport, DriftSeverity


class BlastRadius(StrEnum):
    """Estimated blast radius of a remediation action."""

    NODE = "node"  # Single node/container — low risk
    SERVICE = "service"  # Single service — medium risk
    ZONE = "zone"  # Multiple nodes in a zone — high risk
    MESH = "mesh"  # Network-wide — critical risk


class PatchOp(StrEnum):
    """RFC 6902 JSON Patch operations."""

    ADD = "add"
    REMOVE = "remove"
    REPLACE = "replace"


@dataclass
class RemediationProposal:
    """A single gated remediation proposal.

    Each proposal maps one drift item to one JSON Patch operation.
    The proposal includes a blast-radius estimate so the gate can
    decide whether HITL approval is required.
    """

    # Which drift item this addresses
    drift_item: DriftItem

    # The JSON Patch operation
    op: PatchOp
    path: str  # JSON Pointer path in topology.yaml
    value: Any = None  # The value to add/replace (None for remove)

    # Risk assessment
    blast_radius: BlastRadius = BlastRadius.NODE
    description: str = ""

    # Gate state
    requires_approval: bool = True
    approved: bool = False

    def to_json_patch(self) -> dict[str, Any]:
        """Serialize as an RFC 6902 JSON Patch operation."""
        patch: dict[str, Any] = {"op": self.op.value, "path": self.path}
        if self.op != PatchOp.REMOVE:
            patch["value"] = self.value
        return patch

    def to_dict(self) -> dict[str, Any]:
        """Full serialization including metadata."""
        return {
            "drift": {
                "category": self.drift_item.category.value,
                "severity": self.drift_item.severity.value,
                "entity_type": self.drift_item.entity_type,
                "entity_id": self.drift_item.entity_id,
                "field": self.drift_item.field,
                "message": self.drift_item.message,
            },
            "patch": self.to_json_patch(),
            "blast_radius": self.blast_radius.value,
            "description": self.description,
            "requires_approval": self.requires_approval,
        }


@dataclass
class RemediationPlan:
    """A collection of remediation proposals for a drift report."""

    report: DriftReport
    proposals: list[RemediationProposal] = field(default_factory=list)

    @property
    def requires_hitl(self) -> bool:
        """True if any proposal requires human-in-the-loop approval."""
        return any(p.requires_approval for p in self.proposals)

    @property
    def blast_summary(self) -> dict[str, int]:
        """Count proposals by blast radius."""
        summary: dict[str, int] = {}
        for p in self.proposals:
            key = p.blast_radius.value
            summary[key] = summary.get(key, 0) + 1
        return summary

    def to_dict(self) -> dict[str, Any]:
        """Full serialization."""
        return {
            "topology_file": self.report.topology_file,
            "live_state_file": self.report.live_state_file,
            "generated_at": self.report.generated_at.isoformat(),
            "requires_hitl": self.requires_hitl,
            "blast_summary": self.blast_summary,
            "proposals": [p.to_dict() for p in self.proposals],
        }


def generate_remediation(report: DriftReport) -> RemediationPlan:
    """Generate remediation proposals from a drift report.

    Each drift item is mapped to one JSON Patch operation. The mapping
    follows these rules:

    * MISSING → ``add`` (the entity should exist but doesn't)
    * EXTRA → ``remove`` (the entity exists but shouldn't)
    * MISMATCHED → ``replace`` (the entity exists but has wrong values)

    Blast radius is estimated from entity type:
    * node → NODE (single host/container)
    * service → SERVICE (single workload)
    * link → MESH (network connectivity)
    * zone → ZONE (trust boundary)
    * dependency → SERVICE (operational dependency)
    """
    plan = RemediationPlan(report=report)

    for item in report.items:
        if item.ignored:
            continue

        proposal = _proposal_for(item)
        plan.proposals.append(proposal)

    return plan


def _proposal_for(item: DriftItem) -> RemediationProposal:
    """Map a single drift item to a remediation proposal."""
    entity_type = item.entity_type
    entity_id = item.entity_id

    # Determine patch operation and path
    if item.category == DriftCategory.MISSING:
        op = PatchOp.ADD
        path = f"/{entity_type}s/-"  # append to array
        value = _synthesize_declared(item)
        description = f"Add missing {entity_type} '{entity_id}': {item.message}"
    elif item.category == DriftCategory.EXTRA:
        op = PatchOp.REMOVE
        path = f"/{entity_type}s/{entity_id}"
        value = None
        description = f"Remove extra {entity_type} '{entity_id}': {item.message}"
    else:  # MISMATCHED
        op = PatchOp.REPLACE
        path = f"/{entity_type}s/{entity_id}/{item.field or ''}"
        value = item.declared
        description = (
            f"Fix {entity_type} '{entity_id}' field '{item.field}': "
            f"declared={item.declared!r}, observed={item.observed!r}"
        )

    # Estimate blast radius
    blast = _blast_for(entity_type)

    # Determine if HITL is required
    requires = _requires_hitl(item.severity, blast)

    return RemediationProposal(
        drift_item=item,
        op=op,
        path=path,
        value=value,
        blast_radius=blast,
        description=description,
        requires_approval=requires,
    )


def _blast_for(entity_type: str) -> BlastRadius:
    """Map entity type to blast radius."""
    mapping: dict[str, BlastRadius] = {
        "node": BlastRadius.NODE,
        "service": BlastRadius.SERVICE,
        "link": BlastRadius.MESH,
        "zone": BlastRadius.ZONE,
        "dependency": BlastRadius.SERVICE,
    }
    return mapping.get(entity_type, BlastRadius.NODE)


def _requires_hitl(severity: DriftSeverity, blast: BlastRadius) -> bool:
    """Determine if a proposal requires HITL approval.

    Rules (ADR-0015):
    * CRITICAL severity → always HITL
    * MESH or ZONE blast radius → always HITL
    * WARNING + SERVICE → HITL
    * INFO + NODE → auto-approvable (but still gated by default)
    """
    if severity == DriftSeverity.CRITICAL:
        return True
    if blast in (BlastRadius.MESH, BlastRadius.ZONE):
        return True
    if severity == DriftSeverity.WARNING and blast == BlastRadius.SERVICE:
        return True
    return False


def _synthesize_declared(item: DriftItem) -> dict[str, Any]:
    """Synthesize a minimal declared entity from a drift item.

    For MISSING items, the declared value is what should exist.
    We construct a minimal dict from the entity metadata.
    """
    if item.declared is not None:
        return item.declared if isinstance(item.declared, dict) else {"id": item.entity_id}
    return {"id": item.entity_id}
