"""Command-line interface for rw_blueprint."""

from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

from rw_blueprint.config import get_settings
from rw_blueprint.generator import generate as generate_artifacts
from rw_blueprint.generator import load_topology
from rw_blueprint.live_state import LiveState
from rw_blueprint.probes import ProbeRegistry
from rw_blueprint.reconciler import (
    DriftCategory,
    DriftReport,
    DriftSeverity,
    IgnoreRules,
    Reconciler,
    load_ignore_rules_from_yaml,
)
from rw_blueprint.remediation import generate_remediation
from rw_blueprint.report import DriftReportModel

app = typer.Typer(
    name="rw-blueprint",
    help="Declarative infrastructure source-of-truth engine.",
    no_args_is_help=True,
)

console = Console()
err_console = Console(stderr=True)


@app.command()
def validate(path: str) -> None:
    """Validate a topology YAML file against the schema."""
    try:
        topology = load_topology(path)
    except FileNotFoundError:
        err_console.print(f"[red]Error:[/red] file not found: {path}")
        raise typer.Exit(code=2) from None
    except ValueError as exc:
        err_console.print(f"[red]Validation failed:[/red] {exc}")
        raise typer.Exit(code=2) from None
    console.print(
        f"[green]Valid[/green] topology '{topology.metadata.name}' "
        f"({len(topology.nodes)} nodes, {len(topology.services)} services)."
    )


@app.command()
def generate(
    path: str,
    output: str = typer.Option("", "--output", "-o", help="Output directory (default from config)"),
) -> None:
    """Generate diagrams, docs, and IaC skeletons from a topology YAML file."""
    settings = get_settings()
    if not output:
        output = settings.output.dir
    try:
        topology = load_topology(path)
    except FileNotFoundError:
        err_console.print(f"[red]Error:[/red] file not found: {path}")
        raise typer.Exit(code=2) from None
    except ValueError as exc:
        err_console.print(f"[red]Validation failed:[/red] {exc}")
        raise typer.Exit(code=2) from None
    written = generate_artifacts(topology, output)
    console.print(f"[green]Generated {len(written)} artifact(s)[/green] -> {output}")
    for path_written in written:
        console.print(f"  - {path_written}")


@app.command()
def probe(
    names: list[str] | None = None,
    output: str | None = typer.Option(None, "--output", "-o", help="Write live state to JSON file"),
) -> None:
    """Run probes and collect live state."""
    settings = get_settings()
    registry = ProbeRegistry(timeout=settings.probe.timeout, host_node=settings.host.default_node)
    available = registry.names()

    if names:
        invalid = [n for n in names if n not in available]
        if invalid:
            err_console.print(f"[red]Unknown probes:[/red] {', '.join(invalid)}")
            err_console.print(f"Available: {', '.join(available)}")
            raise typer.Exit(code=2)
        fragment, results = registry.run_selected(names)
    else:
        fragment, results = registry.run_all()

    # Build a LiveState from the fragment (with minimal metadata)
    from datetime import datetime

    from rw_blueprint.live_state import LiveMetadata

    live_state = LiveState(
        metadata=LiveMetadata(captured_at=datetime.now()),
        nodes=fragment.nodes,
        services=fragment.services,
        links=fragment.links,
    )

    if output:
        with open(output, "w") as f:
            json.dump(live_state.model_dump(mode="json"), f, indent=2, default=str)
        console.print(f"[green]Live state written to[/green] {output}")

    # Print summary
    table = Table(title="Probe Results")
    table.add_column("Probe")
    table.add_column("Status")
    table.add_column("Nodes")
    table.add_column("Services")
    table.add_column("Links")
    table.add_column("Errors")
    table.add_column("Duration (ms)")

    for name, result in results.items():
        status = "[green]OK[/green]" if not result.errors else "[red]ERROR[/red]"
        table.add_row(
            name,
            status,
            str(len(result.fragment.nodes)),
            str(len(result.fragment.services)),
            str(len(result.fragment.links)),
            str(len(result.errors)),
            str(result.duration_ms),
        )

    console.print(table)

    if any(r.errors for r in results.values()):
        raise typer.Exit(code=2)


@app.command()
def reconcile(
    topology: str = typer.Argument(..., help="Path to topology YAML file"),
    live_state: str = typer.Argument(..., help="Path to live state JSON file"),
    ignore_rules: str | None = typer.Option(
        None, "--ignore-rules", "-i", help="Path to ignore rules YAML"
    ),
    output: str | None = typer.Option(
        None, "--output", "-o", help="Write drift report to JSON file"
    ),
    format: str = typer.Option(
        "", "--format", "-f", help="Output format: table, json, summary (default from config)"
    ),
    fail_on: str = typer.Option(
        "",
        "--fail-on",
        help="Exit non-zero on severity: critical, warning, info, none (default from config)",
    ),
    remediate: bool = typer.Option(
        False, "--remediate", "-r", help="Generate remediation proposals from drift"
    ),
) -> None:
    """Reconcile declared topology against observed live state."""
    # Resolve config defaults for empty string options
    settings = get_settings()
    if not format:
        format = settings.output.format
    if not fail_on:
        fail_on = settings.reconcile.fail_on

    # Load topology
    try:
        topo = load_topology(topology)
    except FileNotFoundError:
        err_console.print(f"[red]Error:[/red] topology file not found: {topology}")
        raise typer.Exit(code=2) from None
    except (ValueError, Exception) as exc:
        err_console.print(f"[red]Topology validation failed:[/red] {exc}")
        raise typer.Exit(code=2) from None

    # Load live state
    try:
        with open(live_state) as f:
            live_data = json.load(f)
        live = LiveState.model_validate(live_data)
    except FileNotFoundError:
        err_console.print(f"[red]Error:[/red] live state file not found: {live_state}")
        raise typer.Exit(code=2) from None
    except Exception as exc:
        err_console.print(f"[red]Failed to parse live state:[/red] {exc}")
        raise typer.Exit(code=2) from None

    # Load ignore rules
    ignore = IgnoreRules()
    if ignore_rules:
        try:
            ignore = load_ignore_rules_from_yaml(ignore_rules)
        except Exception as exc:
            err_console.print(f"[red]Failed to load ignore rules:[/red] {exc}")
            raise typer.Exit(code=2) from None

    # Run reconciliation
    reconciler = Reconciler(ignore_rules=ignore)
    report = reconciler.reconcile(topo, live)
    report.topology_file = topology
    report.live_state_file = live_state

    # Build typed report model for serialization
    report_model = DriftReportModel.from_drift_report(report)

    # Output
    if format == "json":
        json_str = report_model.model_dump_json_deterministic()
        if output:
            with open(output, "w") as f:
                f.write(json_str)
        else:
            console.print_json(json_str)
    elif format == "summary":
        _print_summary(report)
    else:
        _print_table(report)

    if output and format != "json":
        json_str = report_model.model_dump_json_deterministic()
        with open(output, "w") as f:
            f.write(json_str)
        console.print(f"[green]Drift report written to[/green] {output}")

    # Remediation proposals (ADR-0015: gated, never auto-applied)
    if remediate:
        plan = generate_remediation(report)
        if format == "json":
            import json as _json

            console.print_json(_json.dumps(plan.to_dict()))
        else:
            _print_remediation(plan)
        if plan.requires_hitl:
            console.print("\n[yellow]⚠ Some proposals require human-in-the-loop approval.[/yellow]")

    # Exit code based on severity threshold (ADR-017: 0=clean, 1=drift, 2=error)
    if fail_on != "none":
        severity_order = {"critical": 3, "warning": 2, "info": 1, "none": 0}
        threshold = severity_order.get(fail_on, 3)
        max_severity = 0
        for item in report.items:
            if not item.ignored:
                sev_val = severity_order.get(item.severity.value, 0)
                max_severity = max(max_severity, sev_val)
        if max_severity >= threshold:
            raise typer.Exit(code=1)
    # Exit 0: clean (no drift at/above threshold, or --fail-on none)


def _print_table(report: DriftReport) -> None:
    """Print drift report as a rich table."""
    if not report.items:
        console.print("[green]No drift detected[/green]")
        return

    table = Table(title=f"Drift Report ({report.summary['total']} items)")
    table.add_column("Category")
    table.add_column("Severity")
    table.add_column("Entity")
    table.add_column("ID")
    table.add_column("Field")
    table.add_column("Message")
    table.add_column("Ignored")

    for item in report.items:
        cat_color = {
            DriftCategory.MISSING: "red",
            DriftCategory.EXTRA: "yellow",
            DriftCategory.MISMATCHED: "blue",
        }.get(item.category, "white")

        sev_color = {
            DriftSeverity.CRITICAL: "red",
            DriftSeverity.WARNING: "yellow",
            DriftSeverity.INFO: "blue",
        }.get(item.severity, "white")

        table.add_row(
            f"[{cat_color}]{item.category.value}[/{cat_color}]",
            f"[{sev_color}]{item.severity.value}[/{sev_color}]",
            item.entity_type,
            item.entity_id,
            item.field or "-",
            item.message,
            "yes" if item.ignored else "no",
        )

    console.print(table)

    # Summary
    summary_table = Table(title="Summary")
    summary_table.add_column("Metric")
    summary_table.add_column("Count")
    for key, value in report.summary.items():
        summary_table.add_row(key, str(value))
    console.print(summary_table)


def _print_summary(report: DriftReport) -> None:
    """Print a concise summary."""
    console.print(f"Drift Report: {report.summary['total']} items")
    console.print(f"  Critical: {report.summary['critical']}")
    console.print(f"  Warning:  {report.summary['warning']}")
    console.print(f"  Info:     {report.summary['info']}")
    console.print(f"  Ignored:  {report.summary['ignored']}")
    console.print(f"  Missing:  {report.summary['missing']}")
    console.print(f"  Extra:    {report.summary['extra']}")
    console.print(f"  Mismatched: {report.summary['mismatched']}")


def _print_remediation(plan: object) -> None:
    """Print remediation proposals as a rich table."""
    from rw_blueprint.remediation import RemediationPlan

    if not isinstance(plan, RemediationPlan):
        err_console.print("[red]Internal error:[/red] expected RemediationPlan")
        raise typer.Exit(code=2)

    if not plan.proposals:
        console.print("[green]No remediation needed[/green]")
        return

    table = Table(title=f"Remediation Plan ({len(plan.proposals)} proposals)")
    table.add_column("Op")
    table.add_column("Path")
    table.add_column("Entity")
    table.add_column("Blast Radius")
    table.add_column("HITL")
    table.add_column("Description")

    for p in plan.proposals:
        hitl = "[red]YES[/red]" if p.requires_approval else "[green]no[/green]"
        blast_color = {
            "node": "green",
            "service": "yellow",
            "zone": "red",
            "mesh": "red",
        }.get(p.blast_radius.value, "white")

        table.add_row(
            p.op.value.upper(),
            p.path,
            f"{p.drift_item.entity_type}/{p.drift_item.entity_id}",
            f"[{blast_color}]{p.blast_radius.value}[/{blast_color}]",
            hitl,
            p.description[:80],
        )

    console.print(table)


@app.command()
def mcp(
    transport: str = typer.Option("stdio", "--transport", "-t", help="Transport: stdio or http"),
) -> None:
    """Start the MCP server for agent integration (ADR-0013)."""
    try:
        from rw_blueprint.mcp_server import run as run_mcp
    except ImportError:
        err_console.print("[red]MCP support not installed.[/red] Install with: uv sync --group mcp")
        raise typer.Exit(code=2) from None
    run_mcp(transport)


if __name__ == "__main__":
    app()
