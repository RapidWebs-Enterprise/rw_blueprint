"""Typed, versioned drift report model for JSON serialization.

This module defines the Pydantic v2 models for the serialized drift report
(ADR-0017). The report model is a typed projection of the reconciler's
internal ``DriftReport`` dataclass, carrying a ``report_version`` field
independent of the topology/live-state ``schema_version``.

Design principles:
* ``report_version`` is a stable contract — consumers detect shape changes.
* The model is deterministic (stable field ordering, no ambient state).
* ``generated_at`` is metadata, excluded from byte-stability assertions.
* The model is a pure serialization target — no business logic.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

REPORT_VERSION = "0.1"


class _StrictModel(BaseModel):
    """Base model: forbid unknown fields so typos surface as errors."""

    model_config = ConfigDict(extra="forbid")


class ReportItem(_StrictModel):
    """A single drift finding in the serialized report."""

    category: str  # "missing" | "extra" | "mismatched"
    severity: str  # "critical" | "warning" | "info"
    entity_type: str
    entity_id: str
    field: str | None = None
    declared: Any = None
    observed: Any = None
    message: str = ""
    ignored: bool = False
    ignore_rule: str | None = None


class ReportSummary(_StrictModel):
    """Aggregate counts for the drift report."""

    total: int = 0
    critical: int = 0
    warning: int = 0
    info: int = 0
    ignored: int = 0
    missing: int = 0
    extra: int = 0
    mismatched: int = 0


class DriftReportModel(_StrictModel):
    """Typed, versioned drift report for JSON serialization (ADR-0017).

    This is the stable contract consumed by CI, agents, and downstream
    tooling. It is produced from the reconciler's internal ``DriftReport``
    via ``from_drift_report()``.
    """

    report_version: str = REPORT_VERSION
    topology_file: str = ""
    live_state_file: str | None = None
    generated_at: datetime = Field(default_factory=datetime.now)
    schema_version: str = ""
    summary: ReportSummary = Field(default_factory=ReportSummary)
    items: list[ReportItem] = Field(default_factory=list)

    @classmethod
    def from_drift_report(cls, report: Any) -> DriftReportModel:
        """Convert the reconciler's internal ``DriftReport`` to the typed model."""
        return cls(
            topology_file=report.topology_file,
            live_state_file=report.live_state_file,
            generated_at=report.generated_at,
            schema_version=report.schema_version,
            summary=ReportSummary(**report.summary),
            items=[
                ReportItem(
                    category=item.category.value,
                    severity=item.severity.value,
                    entity_type=item.entity_type,
                    entity_id=item.entity_id,
                    field=item.field,
                    declared=item.declared,
                    observed=item.observed,
                    message=item.message,
                    ignored=item.ignored,
                    ignore_rule=item.ignore_rule,
                )
                for item in report.items
            ],
        )

    def model_dump_json_deterministic(self, **kwargs: Any) -> str:
        """Serialize to deterministic JSON (sorted keys, no trailing newline)."""
        return self.model_dump_json(
            indent=2,
            exclude_none=True,
            **kwargs,
        )
