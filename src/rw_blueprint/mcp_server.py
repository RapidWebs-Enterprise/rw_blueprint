"""MCP server for rw_blueprint (ADR-0013).

Exposes the rw_blueprint engine as MCP tools and resources so that AI agents
(Claude, Hermes, etc.) can consume the source-of-truth engine directly without
shelling out to the CLI.

Uses the mcp v2 API (MCPServer, not FastMCP).

Tools (4):
* validate_topology — validate a topology YAML file
* generate_artifacts — generate diagrams/docs/IaC from a topology
* run_probes — run probes and collect live state
* reconcile_topology — reconcile declared topology against live state

Resources (2):
* topology://{path} — read a topology file
* schema://version — get the current schema version

All tools are read-only by default. The reconcile tool can generate remediation
proposals but never auto-applies them (ADR-0015: apply-is-gated).

Usage:
    uv run rw-blueprint mcp          # stdio transport (default)
    uv run rw-blueprint mcp --http   # HTTP/SSE transport
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from rw_blueprint.generator import generate as generate_artifacts
from rw_blueprint.generator import load_topology
from rw_blueprint.live_state import LiveMetadata, LiveState
from rw_blueprint.probes import ProbeRegistry
from rw_blueprint.reconciler import IgnoreRules, Reconciler
from rw_blueprint.remediation import generate_remediation
from rw_blueprint.report import DriftReportModel
from rw_blueprint.schema import SCHEMA_VERSION

mcp = MCPServer(
    "rw-blueprint",
    description="Declarative infrastructure source-of-truth engine",
)


# ── Tools ────────────────────────────────────────────────────────────────────


@mcp.tool()
def validate_topology(path: str) -> dict[str, Any]:
    """Validate a topology YAML file against the schema.

    Returns a dict with 'valid' (bool), 'name' (str), 'node_count' (int),
    'service_count' (int), and 'error' (str or None).
    """
    try:
        topology = load_topology(path)
    except FileNotFoundError:
        return {"valid": False, "error": f"File not found: {path}"}
    except Exception as exc:
        return {"valid": False, "error": str(exc)}

    return {
        "valid": True,
        "name": topology.metadata.name,
        "node_count": len(topology.nodes),
        "service_count": len(topology.services),
        "link_count": len(topology.links),
        "zone_count": len(topology.zones),
        "dependency_count": len(topology.dependencies),
        "schema_version": SCHEMA_VERSION,
        "error": None,
    }


@mcp.tool()
def generate_artifacts_tool(path: str, output_dir: str = "generated/") -> dict[str, Any]:
    """Generate diagrams, docs, and IaC skeletons from a topology YAML.

    Returns a dict with 'artifact_count' (int), 'artifacts' (list[str]),
    and 'error' (str or None).
    """
    try:
        topology = load_topology(path)
    except FileNotFoundError:
        return {"artifact_count": 0, "artifacts": [], "error": f"File not found: {path}"}
    except Exception as exc:
        return {"artifact_count": 0, "artifacts": [], "error": str(exc)}

    try:
        written = generate_artifacts(topology, output_dir)
    except Exception as exc:
        return {"artifact_count": 0, "artifacts": [], "error": str(exc)}

    return {
        "artifact_count": len(written),
        "artifacts": [str(p) for p in written],
        "output_dir": output_dir,
        "error": None,
    }


@mcp.tool()
def run_probes(
    probe_names: list[str] | None = None,
) -> dict[str, Any]:
    """Run infrastructure probes and collect live state.

    If probe_names is None, all available probes are run.
    Returns a dict with 'nodes', 'services', 'links', 'probe_results',
    and 'error' (str or None).
    """
    registry = ProbeRegistry()
    available = registry.names()

    if probe_names:
        invalid = [n for n in probe_names if n not in available]
        if invalid:
            return {
                "nodes": [],
                "services": [],
                "links": [],
                "probe_results": {},
                "error": f"Unknown probes: {', '.join(invalid)}. Available: {', '.join(available)}",
            }
        fragment, results = registry.run_selected(probe_names)
    else:
        fragment, results = registry.run_all()

    live_state = LiveState(
        metadata=LiveMetadata(captured_at=datetime.now()),
        nodes=fragment.nodes,
        services=fragment.services,
        links=fragment.links,
    )

    probe_results = {}
    for name, result in results.items():
        probe_results[name] = {
            "status": "error" if result.errors else "ok",
            "nodes": len(result.fragment.nodes),
            "services": len(result.fragment.services),
            "links": len(result.fragment.links),
            "errors": result.errors,
            "duration_ms": result.duration_ms,
        }

    return {
        "nodes": live_state.model_dump(mode="json")["nodes"],
        "services": live_state.model_dump(mode="json")["services"],
        "links": live_state.model_dump(mode="json")["links"],
        "probe_results": probe_results,
        "error": None,
    }


@mcp.tool()
def reconcile_topology(
    topology_path: str,
    live_state_path: str,
    ignore_rules_path: str | None = None,
    fail_on: str = "critical",
    include_remediation: bool = False,
) -> dict[str, Any]:
    """Reconcile a declared topology against observed live state.

    Returns a drift report with items, summary, and optional remediation
    proposals. Never auto-applies changes (ADR-0015: apply-is-gated).

    Args:
        topology_path: Path to the topology YAML file.
        live_state_path: Path to the live state JSON file.
        ignore_rules_path: Optional path to ignore rules YAML.
        fail_on: Severity threshold (critical, warning, info, none).
        include_remediation: If True, include remediation proposals.

    Returns a dict with 'topology_file', 'live_state_file', 'summary',
    'items', 'remediation' (if requested), and 'error' (str or None).
    """
    # Load topology
    try:
        topo = load_topology(topology_path)
    except FileNotFoundError:
        return {"error": f"Topology file not found: {topology_path}"}
    except Exception as exc:
        return {"error": f"Topology validation failed: {exc}"}

    # Load live state
    try:
        with open(live_state_path) as f:
            live_data = json.load(f)
        live = LiveState.model_validate(live_data)
    except FileNotFoundError:
        return {"error": f"Live state file not found: {live_state_path}"}
    except Exception as exc:
        return {"error": f"Failed to parse live state: {exc}"}

    # Load ignore rules
    ignore = IgnoreRules()
    if ignore_rules_path:
        try:
            from rw_blueprint.reconciler import load_ignore_rules_from_yaml

            ignore = load_ignore_rules_from_yaml(ignore_rules_path)
        except Exception as exc:
            return {"error": f"Failed to load ignore rules: {exc}"}

    # Run reconciliation
    reconciler = Reconciler(ignore_rules=ignore)
    report = reconciler.reconcile(topo, live)
    report.topology_file = topology_path
    report.live_state_file = live_state_path

    # Build typed report
    report_model = DriftReportModel.from_drift_report(report)

    result: dict[str, Any] = {
        "topology_file": topology_path,
        "live_state_file": live_state_path,
        "summary": report.summary,
        "items": [
            {
                "category": item.category.value,
                "severity": item.severity.value,
                "entity_type": item.entity_type,
                "entity_id": item.entity_id,
                "field": item.field,
                "declared": item.declared,
                "observed": item.observed,
                "message": item.message,
                "ignored": item.ignored,
            }
            for item in report.items
        ],
        "schema_version": report_model.schema_version,
        "error": None,
    }

    # Remediation (optional, gated)
    if include_remediation:
        plan = generate_remediation(report)
        result["remediation"] = {
            "requires_hitl": plan.requires_hitl,
            "blast_summary": plan.blast_summary,
            "proposals": [p.to_dict() for p in plan.proposals],
        }

    return result


# ── Resources ────────────────────────────────────────────────────────────────


@mcp.resource("topology://{path}")
def read_topology(path: str) -> str:
    """Read a topology YAML file as a resource."""
    try:
        return Path(path).read_text()
    except FileNotFoundError:
        return f"# Error: file not found: {path}"
    except Exception as exc:
        return f"# Error: {exc}"


@mcp.resource("schema://version")
def schema_version() -> str:
    """Return the current topology schema version."""
    return SCHEMA_VERSION


# ── Entry point ──────────────────────────────────────────────────────────────


def run(transport: str = "stdio") -> None:
    """Run the MCP server.

    Args:
        transport: "stdio" (default) or "http" for HTTP/SSE.
    """
    if transport == "http":
        asyncio.run(mcp.run_sse_async())
    else:
        asyncio.run(mcp.run_stdio_async())
