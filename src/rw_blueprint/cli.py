"""Command-line interface for rw_blueprint."""

from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

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
        raise typer.Exit(code=1) from None
    except ValueError as exc:
        err_console.print(f"[red]Validation failed:[/red] {exc}")
        raise typer.Exit(code=1) from None
    console.print(
        f"[green]Valid[/green] topology '{topology.metadata.name}' "
        f"({len(topology.nodes)} nodes, {len(topology.services)} services)."
    )


@app.command()
def generate(path: str, output: str = "generated/") -> None:
    """Generate diagrams, docs, and IaC skeletons from a topology YAML file."""
    try:
        topology = load_topology(path)
    except FileNotFoundError:
        err_console.print(f"[red]Error:[/red] file not found: {path}")
        raise typer.Exit(code=1) from None
    except ValueError as exc:
        err_console.print(f"[red]Validation failed:[/red] {exc}")
        raise typer.Exit(code=1) from None
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
    registry = ProbeRegistry()
    available = registry.names()

    if names:
        invalid = [n for n in names if n not in available]
        if invalid:
            err_console.print(f"[red]Unknown probes:[/red] {', '.join(invalid)}")
            err_console.print(f"Available: {', '.join(available)}")
            raise typer.Exit(code=1)
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
        raise typer.Exit(code=1)


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
        "table", "--format", "-f", help="Output format: table, json, summary"
    ),
    fail_on: str = typer.Option(
        "critical", "--fail-on", help="Exit non-zero on severity: critical, warning, info, none"
    ),
) -> None:
    """Reconcile declared topology against observed live state."""
    # Load topology
    try:
        topo = load_topology(topology)
    except FileNotFoundError:
        err_console.print(f"[red]Error:[/red] topology file not found: {topology}")
        raise typer.Exit(code=1) from None
    except ValueError as exc:
        err_console.print(f"[red]Topology validation failed:[/red] {exc}")
        raise typer.Exit(code=1) from None

    # Load live state
    try:
        with open(live_state) as f:
            live_data = json.load(f)
        live = LiveState.model_validate(live_data)
    except FileNotFoundError:
        err_console.print(f"[red]Error:[/red] live state file not found: {live_state}")
        raise typer.Exit(code=1) from None
    except Exception as exc:
        err_console.print(f"[red]Failed to parse live state:[/red] {exc}")
        raise typer.Exit(code=1) from None

    # Load ignore rules
    ignore = IgnoreRules()
    if ignore_rules:
        try:
            ignore = load_ignore_rules_from_yaml(ignore_rules)
        except Exception as exc:
            err_console.print(f"[red]Failed to load ignore rules:[/red] {exc}")
            raise typer.Exit(code=1) from None

    # Run reconciliation
    reconciler = Reconciler(ignore_rules=ignore)
    report = reconciler.reconcile(topo, live)
    report.topology_file = topology
    report.live_state_file = live_state

    # Output
    if format == "json":
        if output:
            with open(output, "w") as f:
                json.dump(report.__dict__, f, indent=2, default=str)
        else:
            console.print_json(json.dumps(report.__dict__, default=str))
    elif format == "summary":
        _print_summary(report)
    else:
        _print_table(report)

    if output and format != "json":
        with open(output, "w") as f:
            json.dump(report.__dict__, f, indent=2, default=str)
        console.print(f"[green]Drift report written to[/green] {output}")

    # Exit code based on severity
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


if __name__ == "__main__":
    app()
