"""Tests for the typed drift report model and exit-code contract."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime

import pydantic
import pytest

from rw_blueprint.reconciler import (
    DriftCategory,
    DriftItem,
    DriftReport,
    DriftSeverity,
)
from rw_blueprint.report import (
    REPORT_VERSION,
    DriftReportModel,
    ReportItem,
    ReportSummary,
)


class TestReportModel:
    """Tests for the typed report model (REQ-004, REQ-007)."""

    def test_report_version_present(self) -> None:
        """REQ-007: report_version is present and independent."""
        report = DriftReportModel(
            topology_file="test.yaml",
            summary=ReportSummary(),
        )
        assert report.report_version == REPORT_VERSION
        assert report.report_version != "0.2"  # independent of schema_version

    def test_from_drift_report_converts_all_fields(self) -> None:
        """Round-trip: internal DriftReport → typed model preserves all data."""
        internal = DriftReport(
            topology_file="topo.yaml",
            live_state_file="live.json",
            schema_version="0.2",
            items=[
                DriftItem(
                    category=DriftCategory.MISSING,
                    severity=DriftSeverity.CRITICAL,
                    entity_type="service",
                    entity_id="honcho",
                    field="image",
                    declared="honcho:latest",
                    observed=None,
                    message="Service 'honcho' is declared but not observed",
                    ignored=False,
                ),
                DriftItem(
                    category=DriftCategory.EXTRA,
                    severity=DriftSeverity.WARNING,
                    entity_type="service",
                    entity_id="ergo",
                    message="Service 'ergo' is observed but not declared",
                    ignored=True,
                    ignore_rule="known-unplanned",
                ),
            ],
        )

        model = DriftReportModel.from_drift_report(internal)

        assert model.report_version == REPORT_VERSION
        assert model.topology_file == "topo.yaml"
        assert model.live_state_file == "live.json"
        assert model.schema_version == "0.2"
        assert model.summary.total == 2
        assert model.summary.critical == 1
        assert model.summary.warning == 1
        assert model.summary.ignored == 1
        assert model.summary.missing == 1
        assert model.summary.extra == 1

        # First item
        assert model.items[0].category == "missing"
        assert model.items[0].severity == "critical"
        assert model.items[0].entity_type == "service"
        assert model.items[0].entity_id == "honcho"
        assert model.items[0].field == "image"
        assert model.items[0].declared == "honcho:latest"
        assert model.items[0].observed is None
        assert model.items[0].ignored is False

        # Second item (ignored)
        assert model.items[1].category == "extra"
        assert model.items[1].ignored is True
        assert model.items[1].ignore_rule == "known-unplanned"

    def test_json_round_trip(self) -> None:
        """JSON serialization round-trips losslessly."""
        model = DriftReportModel(
            topology_file="test.yaml",
            schema_version="0.2",
            summary=ReportSummary(total=1, critical=1),
            items=[
                ReportItem(
                    category="missing",
                    severity="critical",
                    entity_type="service",
                    entity_id="honcho",
                    message="missing",
                ),
            ],
        )

        json_str = model.model_dump_json_deterministic()
        parsed = json.loads(json_str)

        assert parsed["report_version"] == REPORT_VERSION
        assert parsed["topology_file"] == "test.yaml"
        assert parsed["summary"]["total"] == 1
        assert parsed["items"][0]["entity_id"] == "honcho"

    def test_json_deterministic(self) -> None:
        """REQ-008: identical inputs produce byte-identical JSON."""
        model = DriftReportModel(
            topology_file="test.yaml",
            schema_version="0.2",
            summary=ReportSummary(),
        )

        json1 = model.model_dump_json_deterministic()
        json2 = model.model_dump_json_deterministic()

        assert json1 == json2

    def test_empty_report(self) -> None:
        """An empty report (no drift) serializes correctly."""
        internal = DriftReport(
            topology_file="topo.yaml",
            live_state_file="live.json",
            schema_version="0.2",
        )
        model = DriftReportModel.from_drift_report(internal)

        assert model.summary.total == 0
        assert model.items == []

        json_str = model.model_dump_json_deterministic()
        parsed = json.loads(json_str)
        assert parsed["summary"]["total"] == 0

    def test_extra_fields_rejected(self) -> None:
        """Strict schema: unknown fields are rejected."""
        with pytest.raises(pydantic.ValidationError):
            DriftReportModel(
                topology_file="test.yaml",
                summary=ReportSummary(),
                bogus_field="nope",  # type: ignore[call-arg]
            )


class TestExitCodes:
    """Tests for the exit-code contract (REQ-005)."""

    def _run_reconcile(self, *args: str) -> subprocess.CompletedProcess[str]:
        """Run rw-blueprint reconcile and return the process result."""
        return subprocess.run(  # noqa: S603
            [sys.executable, "-m", "rw_blueprint.cli", "reconcile", *args],
            capture_output=True,
            text=True,
            cwd="/home/sysop/Workspaces/rw_blueprint",
        )

    def test_exit_2_on_missing_topology(self) -> None:
        """Exit 2 when topology file doesn't exist."""
        result = self._run_reconcile("nonexistent.yaml", "nonexistent.json")
        assert result.returncode == 2

    def test_exit_2_on_invalid_topology(self, tmp_path: str) -> None:
        """Exit 2 when topology is invalid YAML."""
        bad_yaml = str(tmp_path) + "/bad.yaml"
        with open(bad_yaml, "w") as f:
            f.write("not: valid: yaml: [")
        result = self._run_reconcile(bad_yaml, "nonexistent.json")
        assert result.returncode == 2

    def test_exit_2_on_missing_live_state(self, tmp_path: str) -> None:
        """Exit 2 when live state file doesn't exist."""
        # Need a valid topology first
        import yaml

        from rw_blueprint.schema import Metadata, Topology

        topo = Topology(
            metadata=Metadata(name="test", updated="2026-01-01"),  # type: ignore[arg-type]
        )
        topo_path = str(tmp_path) + "/topo.yaml"
        with open(topo_path, "w") as f:
            yaml.dump(topo.model_dump(mode="json"), f)

        result = self._run_reconcile(topo_path, "nonexistent.json")
        assert result.returncode == 2

    def test_exit_0_on_clean(self, tmp_path: str) -> None:
        """Exit 0 when no drift (declared matches observed)."""
        import yaml

        from rw_blueprint.live_state import LiveMetadata, LiveState
        from rw_blueprint.schema import Metadata, Node, Topology, Zone

        topo = Topology(
            metadata=Metadata(name="test", updated="2026-01-01"),  # type: ignore[arg-type]
            zones=[Zone(id="dmz", name="dmz", description="test zone")],
            nodes=[Node(id="srv1", zone="dmz", type="host")],
        )
        topo_path = str(tmp_path) + "/topo.yaml"
        with open(topo_path, "w") as f:
            yaml.dump(topo.model_dump(mode="json"), f)

        live = LiveState(
            metadata=LiveMetadata(captured_at=datetime.now()),
            nodes=[{"id": "srv1", "type": "host"}],  # type: ignore[list-item]
        )
        live_path = str(tmp_path) + "/live.json"
        with open(live_path, "w") as f:
            json.dump(live.model_dump(mode="json"), f, default=str)

        result = self._run_reconcile(topo_path, live_path, "--fail-on", "critical")
        assert result.returncode == 0

    def test_exit_1_on_drift(self, tmp_path: str) -> None:
        """Exit 1 when drift is present."""
        import yaml

        from rw_blueprint.live_state import LiveMetadata, LiveState
        from rw_blueprint.schema import Metadata, Node, Topology, Zone

        topo = Topology(
            metadata=Metadata(name="test", updated="2026-01-01"),  # type: ignore[arg-type]
            zones=[Zone(id="dmz", name="dmz", description="test zone")],
            nodes=[Node(id="srv1", zone="dmz", type="host")],
        )
        topo_path = str(tmp_path) + "/topo.yaml"
        with open(topo_path, "w") as f:
            yaml.dump(topo.model_dump(mode="json"), f)

        # Live state has an extra node not in topology
        live = LiveState(
            metadata=LiveMetadata(captured_at=datetime.now()),
            nodes=[
                {"id": "srv1", "type": "host"},  # type: ignore[list-item]
                {"id": "ghost", "type": "container"},  # type: ignore[list-item]
            ],
        )
        live_path = str(tmp_path) + "/live.json"
        with open(live_path, "w") as f:
            json.dump(live.model_dump(mode="json"), f, default=str)

        result = self._run_reconcile(topo_path, live_path, "--fail-on", "info")
        assert result.returncode == 1
