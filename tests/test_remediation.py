"""Tests for the remediation proposal engine (ADR-0015)."""

from __future__ import annotations

from rw_blueprint.reconciler import (
    DriftCategory,
    DriftItem,
    DriftReport,
    DriftSeverity,
)
from rw_blueprint.remediation import (
    BlastRadius,
    PatchOp,
    RemediationProposal,
    generate_remediation,
)


class TestRemediationProposal:
    """Unit tests for RemediationProposal."""

    def test_to_json_patch_add(self) -> None:
        """ADD proposals serialize correctly."""
        item = DriftItem(
            category=DriftCategory.MISSING,
            severity=DriftSeverity.CRITICAL,
            entity_type="service",
            entity_id="honcho",
            message="honcho is missing",
        )
        proposal = RemediationProposal(
            drift_item=item,
            op=PatchOp.ADD,
            path="/services/-",
            value={"id": "honcho", "image": "honcho:latest"},
            blast_radius=BlastRadius.SERVICE,
            description="Add honcho service",
        )
        patch = proposal.to_json_patch()
        assert patch == {
            "op": "add",
            "path": "/services/-",
            "value": {"id": "honcho", "image": "honcho:latest"},
        }

    def test_to_json_patch_remove(self) -> None:
        """REMOVE proposals omit value."""
        item = DriftItem(
            category=DriftCategory.EXTRA,
            severity=DriftSeverity.WARNING,
            entity_type="service",
            entity_id="ergo",
            message="ergo is extra",
        )
        proposal = RemediationProposal(
            drift_item=item,
            op=PatchOp.REMOVE,
            path="/services/ergo",
            blast_radius=BlastRadius.SERVICE,
            description="Remove ergo service",
        )
        patch = proposal.to_json_patch()
        assert patch == {"op": "remove", "path": "/services/ergo"}

    def test_to_json_patch_replace(self) -> None:
        """REPLACE proposals include value."""
        item = DriftItem(
            category=DriftCategory.MISMATCHED,
            severity=DriftSeverity.WARNING,
            entity_type="node",
            entity_id="srv1",
            field="public_ip",
            declared="89.167.54.98",
            observed="1.2.3.4",
            message="IP mismatch",
        )
        proposal = RemediationProposal(
            drift_item=item,
            op=PatchOp.REPLACE,
            path="/nodes/srv1/public_ip",
            value="89.167.54.98",
            blast_radius=BlastRadius.NODE,
            description="Fix srv1 public_ip",
        )
        patch = proposal.to_json_patch()
        assert patch == {
            "op": "replace",
            "path": "/nodes/srv1/public_ip",
            "value": "89.167.54.98",
        }

    def test_to_dict_includes_metadata(self) -> None:
        """Full serialization includes drift metadata."""
        item = DriftItem(
            category=DriftCategory.MISSING,
            severity=DriftSeverity.CRITICAL,
            entity_type="service",
            entity_id="honcho",
            message="honcho is missing",
        )
        proposal = RemediationProposal(
            drift_item=item,
            op=PatchOp.ADD,
            path="/services/-",
            blast_radius=BlastRadius.SERVICE,
            description="Add honcho",
        )
        d = proposal.to_dict()
        assert d["drift"]["category"] == "missing"
        assert d["drift"]["severity"] == "critical"
        assert d["patch"]["op"] == "add"
        assert d["blast_radius"] == "service"
        assert d["requires_approval"] is True


class TestRemediationPlan:
    """Unit tests for RemediationPlan."""

    def test_empty_plan(self) -> None:
        """Empty report produces empty plan."""
        report = DriftReport(topology_file="test.yaml", live_state_file=None)
        plan = generate_remediation(report)
        assert len(plan.proposals) == 0
        assert plan.requires_hitl is False

    def test_ignored_items_skipped(self) -> None:
        """Ignored drift items are excluded from remediation."""
        report = DriftReport(topology_file="test.yaml", live_state_file=None)
        report.add_item(
            DriftItem(
                category=DriftCategory.EXTRA,
                severity=DriftSeverity.INFO,
                entity_type="node",
                entity_id="ghost",
                message="extra node",
                ignored=True,
            )
        )
        plan = generate_remediation(report)
        assert len(plan.proposals) == 0

    def test_missing_becomes_add(self) -> None:
        """MISSING drift → ADD patch."""
        report = DriftReport(topology_file="test.yaml", live_state_file=None)
        report.add_item(
            DriftItem(
                category=DriftCategory.MISSING,
                severity=DriftSeverity.CRITICAL,
                entity_type="service",
                entity_id="honcho",
                message="honcho is missing",
            )
        )
        plan = generate_remediation(report)
        assert len(plan.proposals) == 1
        assert plan.proposals[0].op == PatchOp.ADD
        assert plan.proposals[0].path == "/services/-"

    def test_extra_becomes_remove(self) -> None:
        """EXTRA drift → REMOVE patch."""
        report = DriftReport(topology_file="test.yaml", live_state_file=None)
        report.add_item(
            DriftItem(
                category=DriftCategory.EXTRA,
                severity=DriftSeverity.WARNING,
                entity_type="service",
                entity_id="ergo",
                message="ergo is extra",
            )
        )
        plan = generate_remediation(report)
        assert len(plan.proposals) == 1
        assert plan.proposals[0].op == PatchOp.REMOVE
        assert plan.proposals[0].path == "/services/ergo"

    def test_mismatched_becomes_replace(self) -> None:
        """MISMATCHED drift → REPLACE patch."""
        report = DriftReport(topology_file="test.yaml", live_state_file=None)
        report.add_item(
            DriftItem(
                category=DriftCategory.MISMATCHED,
                severity=DriftSeverity.WARNING,
                entity_type="node",
                entity_id="srv1",
                field="public_ip",
                declared="89.167.54.98",
                observed="1.2.3.4",
                message="IP mismatch",
            )
        )
        plan = generate_remediation(report)
        assert len(plan.proposals) == 1
        assert plan.proposals[0].op == PatchOp.REPLACE
        assert plan.proposals[0].path == "/nodes/srv1/public_ip"

    def test_blast_radius_mapping(self) -> None:
        """Entity types map to correct blast radii."""
        report = DriftReport(topology_file="test.yaml", live_state_file=None)
        for entity_type, expected in [
            ("node", BlastRadius.NODE),
            ("service", BlastRadius.SERVICE),
            ("link", BlastRadius.MESH),
            ("zone", BlastRadius.ZONE),
            ("dependency", BlastRadius.SERVICE),
        ]:
            report.items = []
            report.add_item(
                DriftItem(
                    category=DriftCategory.MISSING,
                    severity=DriftSeverity.WARNING,
                    entity_type=entity_type,
                    entity_id="test",
                    message="test",
                )
            )
            plan = generate_remediation(report)
            assert plan.proposals[0].blast_radius == expected, f"{entity_type} → {expected}"

    def test_hitl_required_for_critical(self) -> None:
        """CRITICAL severity always requires HITL."""
        report = DriftReport(topology_file="test.yaml", live_state_file=None)
        report.add_item(
            DriftItem(
                category=DriftCategory.MISSING,
                severity=DriftSeverity.CRITICAL,
                entity_type="node",
                entity_id="srv1",
                message="critical missing node",
            )
        )
        plan = generate_remediation(report)
        assert plan.requires_hitl is True
        assert plan.proposals[0].requires_approval is True

    def test_hitl_required_for_mesh_blast(self) -> None:
        """MESH blast radius always requires HITL."""
        report = DriftReport(topology_file="test.yaml", live_state_file=None)
        report.add_item(
            DriftItem(
                category=DriftCategory.MISMATCHED,
                severity=DriftSeverity.INFO,
                entity_type="link",
                entity_id="cloudflare-to-srv1",
                field="to",
                message="link mismatch",
            )
        )
        plan = generate_remediation(report)
        assert plan.requires_hitl is True

    def test_info_node_auto_approvable(self) -> None:
        """INFO severity + NODE blast = auto-approvable."""
        report = DriftReport(topology_file="test.yaml", live_state_file=None)
        report.add_item(
            DriftItem(
                category=DriftCategory.EXTRA,
                severity=DriftSeverity.INFO,
                entity_type="node",
                entity_id="ghost",
                message="extra node",
            )
        )
        plan = generate_remediation(report)
        assert plan.proposals[0].requires_approval is False

    def test_blast_summary(self) -> None:
        """Blast summary counts proposals by radius."""
        report = DriftReport(topology_file="test.yaml", live_state_file=None)
        report.add_item(
            DriftItem(
                category=DriftCategory.MISSING,
                severity=DriftSeverity.WARNING,
                entity_type="node",
                entity_id="n1",
                message="missing node",
            )
        )
        report.add_item(
            DriftItem(
                category=DriftCategory.MISSING,
                severity=DriftSeverity.WARNING,
                entity_type="service",
                entity_id="s1",
                message="missing service",
            )
        )
        plan = generate_remediation(report)
        summary = plan.blast_summary
        assert summary["node"] == 1
        assert summary["service"] == 1

    def test_to_dict_full(self) -> None:
        """Full plan serialization is correct."""
        report = DriftReport(topology_file="test.yaml", live_state_file="live.json")
        report.add_item(
            DriftItem(
                category=DriftCategory.MISSING,
                severity=DriftSeverity.CRITICAL,
                entity_type="service",
                entity_id="honcho",
                message="honcho is missing",
            )
        )
        plan = generate_remediation(report)
        d = plan.to_dict()
        assert d["topology_file"] == "test.yaml"
        assert d["live_state_file"] == "live.json"
        assert d["requires_hitl"] is True
        assert len(d["proposals"]) == 1
        assert d["proposals"][0]["patch"]["op"] == "add"
