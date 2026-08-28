"""Reconciler: declared vs. live state diff engine.

This module implements the reconciler (ADR-0008, ADR-0009) — the core
drift-detection engine that compares a declared topology against an
observed live state and produces a structured drift report.

The reconciler follows the Kubernetes control-loop pattern:
* Level-triggered (not edge-triggered) — always computes full diff
* Idempotent — same inputs always produce same output
* Three-way classification: missing, extra, mismatched
* Severity classification: critical, warning, info
* Ignore rules for known/acceptable drift
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from rw_blueprint.live_state import LiveState
from rw_blueprint.schema import Topology

if TYPE_CHECKING:
    pass


class DriftCategory(StrEnum):
    """Three-way drift classification (ADR-0008)."""

    MISSING = "missing"  # declared but not observed
    EXTRA = "extra"  # observed but not declared
    MISMATCHED = "mismatched"  # both exist but differ


class DriftSeverity(StrEnum):
    """Drift severity levels."""

    CRITICAL = "critical"  # breaks functionality, security risk
    WARNING = "warning"  # degraded but functional
    INFO = "info"  # informational, no immediate impact


@dataclass
class DriftItem:
    """A single drift finding."""

    category: DriftCategory
    severity: DriftSeverity
    entity_type: str  # "node", "service", "link", "zone", "dependency"
    entity_id: str
    field: str | None = None
    declared: Any = None
    observed: Any = None
    message: str = ""
    ignored: bool = False
    ignore_rule: str | None = None


@dataclass
class DriftReport:
    """Complete drift report from a reconciliation run."""

    topology_file: str
    live_state_file: str | None
    generated_at: datetime = field(default_factory=datetime.now)
    schema_version: str = ""
    items: list[DriftItem] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._recompute_summary()

    def _recompute_summary(self) -> None:
        self.summary = {
            "total": len(self.items),
            "critical": sum(1 for i in self.items if i.severity == DriftSeverity.CRITICAL),
            "warning": sum(1 for i in self.items if i.severity == DriftSeverity.WARNING),
            "info": sum(1 for i in self.items if i.severity == DriftSeverity.INFO),
            "ignored": sum(1 for i in self.items if i.ignored),
            "missing": sum(1 for i in self.items if i.category == DriftCategory.MISSING),
            "extra": sum(1 for i in self.items if i.category == DriftCategory.EXTRA),
            "mismatched": sum(1 for i in self.items if i.category == DriftCategory.MISMATCHED),
        }

    def add_item(self, item: DriftItem) -> None:
        self.items.append(item)
        self._recompute_summary()

    def filter_ignored(self) -> DriftReport:
        """Return a new report with ignored items removed."""
        filtered = DriftReport(
            topology_file=self.topology_file,
            live_state_file=self.live_state_file,
            generated_at=self.generated_at,
            schema_version=self.schema_version,
            items=[i for i in self.items if not i.ignored],
        )
        return filtered


class IgnoreRule:
    """A rule for ignoring specific drift patterns."""

    def __init__(
        self,
        name: str,
        entity_type: str | None = None,
        entity_id_pattern: str | None = None,
        field: str | None = None,
        category: DriftCategory | None = None,
    ):
        self.name = name
        self.entity_type = entity_type
        self.entity_id_pattern = entity_id_pattern
        self.field = field
        self.category = category

    def matches(self, item: DriftItem) -> bool:
        if self.entity_type and item.entity_type != self.entity_type:
            return False
        if self.entity_id_pattern:
            import fnmatch

            if not fnmatch.fnmatch(item.entity_id, self.entity_id_pattern):
                return False
        if self.field and item.field != self.field:
            return False
        if self.category and item.category != self.category:
            return False
        return True


class IgnoreRules:
    """Collection of ignore rules."""

    def __init__(self, rules: list[IgnoreRule] | None = None):
        self.rules = rules or []

    def apply(self, report: DriftReport) -> DriftReport:
        """Apply ignore rules to a report, marking matching items as ignored."""
        for item in report.items:
            for rule in self.rules:
                if rule.matches(item):
                    item.ignored = True
                    item.ignore_rule = rule.name
                    break
        report._recompute_summary()
        return report


class Reconciler:
    """Reconciles declared topology against observed live state."""

    def __init__(
        self,
        ignore_rules: IgnoreRules | None = None,
        severity_overrides: dict[str, DriftSeverity] | None = None,
    ):
        self.ignore_rules = ignore_rules or IgnoreRules()
        self.severity_overrides = severity_overrides or {}

    def reconcile(
        self,
        topology: Topology,
        live_state: LiveState,
    ) -> DriftReport:
        """Perform full reconciliation and return a drift report."""
        report = DriftReport(
            topology_file="",
            live_state_file="",
            schema_version=topology.schema_version,
        )

        # Build lookup maps
        declared_nodes = {n.id: n for n in topology.nodes}
        declared_services = {s.id: s for s in topology.services}
        declared_links = {link.id: link for link in topology.links}
        declared_zones = {z.id: z for z in topology.zones}
        declared_deps = {d.id: d for d in topology.dependencies}

        observed_nodes = {n.id: n for n in live_state.nodes}
        observed_services = {s.id: s for s in live_state.services}
        observed_links = {link.id: link for link in live_state.links}

        # --- Nodes ---
        self._diff_entities(
            report,
            "node",
            declared_nodes,
            observed_nodes,
            self._compare_nodes,
        )

        # --- Services ---
        self._diff_entities(
            report,
            "service",
            declared_services,
            observed_services,
            self._compare_services,
        )

        # --- Links ---
        self._diff_entities(
            report,
            "link",
            declared_links,
            observed_links,
            self._compare_links,
        )

        # --- Zones (declared only, not observable) ---
        for zone_id, _zone in declared_zones.items():
            report.add_item(
                DriftItem(
                    category=DriftCategory.MISSING,
                    severity=DriftSeverity.INFO,
                    entity_type="zone",
                    entity_id=zone_id,
                    message=f"Zone '{zone_id}' is a design-time construct (not observable)",
                )
            )

        # --- Dependencies (declared only, not observable) ---
        for dep_id, _dep in declared_deps.items():
            report.add_item(
                DriftItem(
                    category=DriftCategory.MISSING,
                    severity=DriftSeverity.INFO,
                    entity_type="dependency",
                    entity_id=dep_id,
                    message=f"Dependency '{dep_id}' is a logical construct (not observable)",
                )
            )

        # Apply ignore rules
        self.ignore_rules.apply(report)

        return report

    def _diff_entities(
        self,
        report: DriftReport,
        entity_type: str,
        declared: dict[str, Any],
        observed: dict[str, Any],
        compare_fn: Callable[[DriftReport, str, Any, Any], None],
    ) -> None:
        """Generic three-way diff for a single entity type."""
        all_ids = set(declared.keys()) | set(observed.keys())

        for entity_id in sorted(all_ids):
            decl = declared.get(entity_id)
            obs = observed.get(entity_id)

            if decl is not None and obs is None:
                # Missing: declared but not observed
                severity = self._severity_for(entity_type, "missing", entity_id)
                report.add_item(
                    DriftItem(
                        category=DriftCategory.MISSING,
                        severity=severity,
                        entity_type=entity_type,
                        entity_id=entity_id,
                        message=(
                            f"{entity_type.capitalize()} '{entity_id}' is declared but not observed"
                        ),
                    )
                )
            elif decl is None and obs is not None:
                # Extra: observed but not declared
                severity = self._severity_for(entity_type, "extra", entity_id)
                report.add_item(
                    DriftItem(
                        category=DriftCategory.EXTRA,
                        severity=severity,
                        entity_type=entity_type,
                        entity_id=entity_id,
                        message=(
                            f"{entity_type.capitalize()} '{entity_id}' is observed but not declared"
                        ),
                    )
                )
            else:
                # Both exist — compare fields
                compare_fn(report, entity_id, decl, obs)

    def _compare_nodes(self, report: DriftReport, entity_id: str, decl: Any, obs: Any) -> None:
        """Compare two Node objects field by field."""
        fields = [
            ("type", decl.type, obs.type),
            ("provider", decl.provider, obs.provider),
            ("public_ip", decl.public_ip, obs.public_ip),
            ("tailscale_ip", decl.tailscale_ip, obs.tailscale_ip),
            ("host", decl.host, obs.host),
            ("cpu", decl.cpu, obs.cpu),
            ("memory", decl.memory, obs.memory),
        ]
        for field_name, decl_val, obs_val in fields:
            if decl_val != obs_val:
                severity = self._severity_for("node", "mismatch", entity_id, field_name)
                report.add_item(
                    DriftItem(
                        category=DriftCategory.MISMATCHED,
                        severity=severity,
                        entity_type="node",
                        entity_id=entity_id,
                        field=field_name,
                        declared=decl_val,
                        observed=obs_val,
                        message=(
                            f"Node '{entity_id}' field '{field_name}' differs: "
                            f"declared={decl_val}, observed={obs_val}"
                        ),
                    )
                )

    def _compare_services(self, report: DriftReport, entity_id: str, decl: Any, obs: Any) -> None:
        """Compare two Service objects field by field."""
        # Compare scalar fields
        scalar_fields = [
            ("node", decl.node, obs.node),
            ("kind", decl.kind, obs.kind),
            ("image", decl.image, obs.image),
            ("managed_by", decl.managed_by, obs.managed_by),
        ]
        for field_name, decl_val, obs_val in scalar_fields:
            if decl_val != obs_val:
                severity = self._severity_for("service", "mismatch", entity_id, field_name)
                report.add_item(
                    DriftItem(
                        category=DriftCategory.MISMATCHED,
                        severity=severity,
                        entity_type="service",
                        entity_id=entity_id,
                        field=field_name,
                        declared=decl_val,
                        observed=obs_val,
                        message=(
                            f"Service '{entity_id}' field '{field_name}' differs: "
                            f"declared={decl_val}, observed={obs_val}"
                        ),
                    )
                )

        # Compare ports (list of Port objects)
        decl_ports = {(p.port, p.protocol): p for p in decl.ports}
        obs_ports = {(p.port, p.protocol): p for p in obs.ports}
        all_port_keys = set(decl_ports.keys()) | set(obs_ports.keys())

        for port_key in sorted(all_port_keys):
            decl_port = decl_ports.get(port_key)
            obs_port = obs_ports.get(port_key)

            if decl_port is not None and obs_port is None:
                severity = self._severity_for("service", "missing", entity_id, f"port:{port_key}")
                report.add_item(
                    DriftItem(
                        category=DriftCategory.MISSING,
                        severity=severity,
                        entity_type="service",
                        entity_id=entity_id,
                        field=f"port:{port_key}",
                        message=f"Service '{entity_id}' port {port_key} declared but not observed",
                    )
                )
            elif decl_port is None and obs_port is not None:
                severity = self._severity_for("service", "extra", entity_id, f"port:{port_key}")
                report.add_item(
                    DriftItem(
                        category=DriftCategory.EXTRA,
                        severity=severity,
                        entity_type="service",
                        entity_id=entity_id,
                        field=f"port:{port_key}",
                        message=f"Service '{entity_id}' port {port_key} observed but not declared",
                    )
                )
            else:
                # Compare port fields - both are guaranteed non-None here
                # Type narrowing: both are non-None in this branch
                if decl_port is None or obs_port is None:
                    continue
                if decl_port.public != obs_port.public:
                    severity = self._severity_for(
                        "service", "mismatch", entity_id, f"port:{port_key}.public"
                    )
                    report.add_item(
                        DriftItem(
                            category=DriftCategory.MISMATCHED,
                            severity=severity,
                            entity_type="service",
                            entity_id=entity_id,
                            field=f"port:{port_key}.public",
                            declared=decl_port.public,
                            observed=obs_port.public,
                            message=(
                                f"Service '{entity_id}' port {port_key} public mapping differs"
                            ),
                        )
                    )

    def _compare_links(self, report: DriftReport, entity_id: str, decl: Any, obs: Any) -> None:
        """Compare two Link objects field by field."""
        fields = [
            ("from", decl.from_, obs.from_),
            ("to", decl.to, obs.to),
            ("protocol", decl.protocol, obs.protocol),
        ]
        for field_name, decl_val, obs_val in fields:
            if decl_val != obs_val:
                severity = self._severity_for("link", "mismatch", entity_id, field_name)
                report.add_item(
                    DriftItem(
                        category=DriftCategory.MISMATCHED,
                        severity=severity,
                        entity_type="link",
                        entity_id=entity_id,
                        field=field_name,
                        declared=decl_val,
                        observed=obs_val,
                        message=(
                            f"Link '{entity_id}' field '{field_name}' differs: "
                            f"declared={decl_val}, observed={obs_val}"
                        ),
                    )
                )

    def _severity_for(
        self,
        entity_type: str,
        category: str,
        entity_id: str,
        field: str | None = None,
    ) -> DriftSeverity:
        """Determine severity for a drift item."""
        # Check for explicit override
        key = f"{entity_type}.{entity_id}"
        if field:
            key += f".{field}"
        if key in self.severity_overrides:
            return self.severity_overrides[key]

        # Default severity rules
        if category == "missing":
            if entity_type in ("service", "link"):
                return DriftSeverity.CRITICAL
            return DriftSeverity.WARNING
        elif category == "extra":
            if entity_type == "service":
                return DriftSeverity.WARNING  # unplanned service
            return DriftSeverity.INFO
        else:  # mismatched
            if entity_type == "service" and field in ("image", "managed_by", "node"):
                return DriftSeverity.CRITICAL
            if entity_type == "link" and field in ("from", "to"):
                return DriftSeverity.CRITICAL
            return DriftSeverity.WARNING


def load_ignore_rules_from_yaml(path: str) -> IgnoreRules:
    """Load ignore rules from a YAML file."""
    import yaml

    with open(path) as f:
        data = yaml.safe_load(f)

    rules = []
    for rule_data in data.get("ignore_rules", []):
        rules.append(
            IgnoreRule(
                name=rule_data["name"],
                entity_type=rule_data.get("entity_type"),
                entity_id_pattern=rule_data.get("entity_id_pattern"),
                field=rule_data.get("field"),
                category=DriftCategory(rule_data["category"])
                if rule_data.get("category")
                else None,
            )
        )
    return IgnoreRules(rules)
