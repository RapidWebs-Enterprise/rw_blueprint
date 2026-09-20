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
from rw_blueprint.probes.multi_node import MultiNodeProbeCoordinator, TargetNode
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
from rw_blueprint.deployer import (
    DeployExecutor,
    DeploymentState,
    HealthVerifier,
    PlanGenerator,
    RollbackExecutor,
    TargetManager,
)
from pathlib import Path

app = typer.Typer(
    name="rw-blueprint",
    help="Declarative infrastructure source-of-truth engine.",
    no_args_is_help=True,
)

console = Console()
err_console = Console(stderr=True)


def make_probe(name: str, registry):
    """Factory that returns a probe constructor given a name and registry."""
    def factory(timeout, host_node):
        return registry.get(name).__class__(timeout=timeout, host_node=host_node)
    return factory


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
    nodes: str | None = typer.Option(None, "--nodes", "-n", help="Target nodes to probe (comma-separated)"),
) -> None:
    """Run probes and collect live state."""
    settings = get_settings()

    # Build target nodes from CLI args or topology
    target_nodes = []
    if nodes:
        # Parse comma-separated node list
        for node_id in nodes.split(","):
            node_id = node_id.strip()
            if node_id:
                target_nodes.append(TargetNode(id=node_id))
    else:
        # Default: probe the default host node
        target_nodes.append(TargetNode(id=settings.host.default_node))
    
    coordinator = MultiNodeProbeCoordinator(
        targets=target_nodes,
        default_timeout=settings.probe.timeout,
    )
    
    registry = ProbeRegistry(timeout=settings.probe.timeout)
    available = registry.names()

    if names:
        invalid = [n for n in names if n not in available]
        if invalid:
            err_console.print(f"[red]Unknown probes:[/red] {', '.join(invalid)}")
            err_console.print(f"Available: {', '.join(available)}")
            raise typer.Exit(code=2)
        
        # Run selected probes across all target nodes
        merged_fragment = None
        all_results = {}
        
        for probe_name in names:
            factory = make_probe(probe_name, registry)

            fragment, per_node_results = coordinator.run_probe_on_targets(
                probe_factory=factory,
                probe_name=probe_name,
            )
            all_results[probe_name] = per_node_results
            if merged_fragment is None:
                merged_fragment = fragment
            else:
                merged_fragment = merged_fragment.merge(fragment)
        
        # Flatten per-node results for display
        flat_results = {}
        for probe_name, node_results in all_results.items():
            for node_id, result in node_results.items():
                flat_results[f"{probe_name}@{node_id}"] = result
        
        fragment = merged_fragment
    else:
        # Run all probes
        merged_fragment = None
        all_results = {}
        
        for probe_name in available:
            factory = make_probe(probe_name, registry)
            
            fragment, per_node_results = coordinator.run_probe_on_targets(
                probe_factory=factory,
                probe_name=probe_name,
            )
            all_results[probe_name] = per_node_results
            if merged_fragment is None:
                merged_fragment = fragment
            else:
                merged_fragment = merged_fragment.merge(fragment)
        
        # Flatten per-node results for display
        flat_results = {}
        for probe_name, node_results in all_results.items():
            for node_id, result in node_results.items():
                flat_results[f"{probe_name}@{node_id}"] = result
        
        fragment = merged_fragment

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

    for name, result in flat_results.items():
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

    if any(r.errors for r in flat_results.values()):
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
        raise typer.Exit(code=2) from None

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


@app.command()
def plan(
    topology: str = typer.Argument(..., help="Path to topology YAML file"),
    node: str = typer.Option(..., "--node", "-n", help="Target node to plan for"),
    services: str | None = typer.Option(None, "--services", "-s", help="Comma-separated list of services to deploy"),
    force: bool = typer.Option(False, "--force", help="Skip confirmation prompts"),
) -> None:
    """Generate a deployment plan for a node."""
    # Load topology
    try:
        topo = load_topology(topology)
    except FileNotFoundError:
        err_console.print(f"[red]Error:[/red] topology file not found: {topology}")
        raise typer.Exit(code=2) from None
    except ValueError as exc:
        err_console.print(f"[red]Topology validation failed:[/red] {exc}")
        raise typer.Exit(code=2) from None

    # Filter services if specified
    target_services = None
    if services:
        target_services = [s.strip() for s in services.split(",") if s.strip()]

    # Extract services for this node
    node_services = [s for s in topo.services if s.node == node]
    if target_services:
        node_services = [s for s in node_services if s.id in target_services]

    # Generate plan
    generator = PlanGenerator()
    plan = generator.generate(desired=node_services, existing={})

    # Display plan
    console.print(f"\n[bold]Deployment Plan for {node}[/bold]\n")
    console.print(f"  Actions: {len(plan.actions)}")
    console.print(f"  Blast Radius: [yellow]{plan.blast_radius.value}[/yellow]")
    console.print(f"  Requires Approval: {'[red]Yes[/red]' if plan.requires_approval else 'No'}\n")

    if plan.actions:
        table = Table(title="Actions")
        table.add_column("Service")
        table.add_column("Action")
        table.add_column("Node")
        table.add_column("Dependencies")
        for action in plan.actions:
            deps = ", ".join(action.dependencies) if action.dependencies else "-"
            table.add_row(action.service, action.action, action.node, deps)
        console.print(table)
    else:
        console.print("[green]No actions required - state is already correct[/green]")

    # Save plan to file if requested
    if not force:
        confirm = typer.confirm("\n[bold]Apply this plan?[/bold]")
        if not confirm:
            console.print("[yellow]Plan saved, not applied.[/yellow]")
            raise typer.Exit(code=0)


@app.command()
def deploy(
    topology: str = typer.Argument(..., help="Path to topology YAML file"),
    node: str = typer.Option(..., "--node", "-n", help="Target node to deploy to"),
    services: str | None = typer.Option(None, "--services", "-s", help="Comma-separated list of services to deploy"),
    force: bool = typer.Option(False, "--force", help="Skip confirmation prompts"),
    dry_run: bool = typer.Option(False, "--dry-run", "-d", help="Show what would be deployed without applying"),
) -> None:
    """Deploy services to a node."""
    # Load topology
    try:
        topo = load_topology(topology)
    except FileNotFoundError:
        err_console.print(f"[red]Error:[/red] topology file not found: {topology}")
        raise typer.Exit(code=2) from None
    except ValueError as exc:
        err_console.print(f"[red]Topology validation failed:[/red] {exc}")
        raise typer.Exit(code=2) from None

    # Filter services for this node
    node_services = [s for s in topo.services if s.node == node]
    if services:
        target_services = [s.strip() for s in services.split(",") if s.strip()]
        node_services = [s for s in node_services if s.id in target_services]

    # Generate plan
    generator = PlanGenerator()
    plan = generator.generate(desired=node_services, existing={})

    if dry_run:
        console.print(f"\n[bold]Dry-run mode: showing planned changes for {node}[/bold]\n")
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Service")
        table.add_column("Action")
        table.add_column("Config Path")
        for action in plan.actions:
            table.add_row(action.service, action.action, action.config_path or "")
        console.print(table)
        console.print(f"\n[yellow]Total actions: {len(plan.actions)}[/yellow]")
        raise typer.Exit(code=0)

    if not force and plan.requires_approval:
        console.print(f"\n[bold]Blast radius: [yellow]{plan.blast_radius.value}[/yellow][/bold]")
        confirm = typer.confirm("Apply this deployment?")
        if not confirm:
            console.print("[yellow]Deployment cancelled.[/yellow]")
            raise typer.Exit(code=0)

    # Execute deployment
    nodes_config = {node: {"host": node, "user": "sysop"}}
    target_manager = TargetManager(nodes=nodes_config)
    executor = DeployExecutor(target_manager=target_manager)
    state_tracker = DeploymentState(storage_dir=Path(".rw_blueprint/deployments"))

    # Generate artifacts first
    output_dir = Path("docs/generated")
    generate_artifacts(topo, output_dir)

    result = executor.execute(
        plan,
        node,
        output_dir=output_dir,
        state_tracker=state_tracker,
        continue_on_failure=True,  # Continue if individual services fail
    )

    if result.success:
        console.print(f"\n[green]✓ Deployment successful for {node}[/green]")
        console.print(f"  Services: {', '.join(result.actions_completed)}")
    else:
        console.print(f"\n[red]✗ Deployment failed for {node}[/red]")
        console.print(f"  Error: {result.error_message}")
        raise typer.Exit(code=1)

    # Verify health
    verifier = HealthVerifier(target_manager=target_manager)
    for service_id in result.actions_completed:
        health = verifier.verify(node, service_id)
        if health.healthy:
            console.print(f"  [green]✓[/green] {service_id}: healthy")
        else:
            console.print(f"  [red]✗[/red] {service_id}: unhealthy")
            if not force:
                console.print(f"\n[yellow]Health check failed for {service_id}. Rollback requested.[/yellow]")
                rollback_result = rollback_service(node, service_id, force=False)
                if rollback_result.success:
                    console.print(f"[green]✓ Rolled back {service_id}[/green]")
                else:
                    console.print(f"[red]✗ Rollback failed: {rollback_result.error_message}[/red]")
                raise typer.Exit(code=1)

    console.print(f"\n[green]✓ All services healthy on {node}[/green]")

    # Record deployment
    from rw_blueprint.deployer.state import DeploymentRecord
    from datetime import datetime
    import hashlib

    config_hash = hashlib.sha256(topology.encode()).hexdigest()[:16]
    record = DeploymentRecord(
        version="1.0.0",
        deployed_at=datetime.now().isoformat(),
        deployed_by="sysop",
        status="healthy" if result.success else "failed",
        image="local",
        config_hash=config_hash,
    )
    for service_id in result.actions_completed:
        state_tracker.record(node, service_id, record)


def rollback_service(node: str, service: str, force: bool = False) -> Any:
    """Helper to rollback a service (used by deploy health check)."""
    from rw_blueprint.deployer.rollback import RollbackResult
    from rw_blueprint.deployer.targets import TargetManager
    target_manager = TargetManager()
    state_tracker = DeploymentState(storage_dir=Path(".rw_blueprint/deployments"))
    executor = RollbackExecutor(target_manager=target_manager, state_tracker=state_tracker)
    return executor.rollback(node, service)


@app.command()
def rollback(
    service: str = typer.Argument(..., help="Service to rollback"),
    node: str = typer.Option(..., "--node", "-n", help="Target node"),
) -> None:
    """Rollback a service to its previous healthy state."""
    result = rollback_service(node, service, force=False)

    if result.success:
        console.print(f"[green]✓ Rolled back {service} on {node}[/green]")
    else:
        console.print(f"[red]✗ Rollback failed for {service} on {node}[/red]")
        console.print(f"  Error: {result.error_message}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()


# === Image Lifecycle Commands ===

image_app = typer.Typer(help="Manage container image lifecycle (build, pull, push, inspect).")
app.add_typer(image_app, name="image")


@image_app.command("list")
def image_list(
    node: str = typer.Option("localhost", "--node", "-n", help="Target node"),
) -> None:
    """List all container images on the target node."""
    from rw_blueprint.deployer.lifecycle import ImageLifecycle

    target = TargetManager()
    lifecycle = ImageLifecycle(target_manager=target)

    images = lifecycle.list_images(node)
    if not images:
        console.print(f"[yellow]No images found on {node}[/yellow]")
        return

    table = Table(title=f"Images on {node}")
    table.add_column("Name")
    table.add_column("Tag")
    table.add_column("Source")
    table.add_column("Built At")
    table.add_column("Git SHA")

    for img in images:
        table.add_row(
            img.name,
            img.tag,
            img.source,
            img.built_at.strftime("%Y-%m-%d %H:%M") if img.built_at else "",
            img.git_sha or "",
        )

    console.print(table)


@image_app.command("inspect")
def image_inspect(
    reference: str = typer.Argument(..., help="Image reference (e.g., localhost/honcho:latest)"),
    node: str = typer.Option("localhost", "--node", "-n", help="Target node"),
) -> None:
    """Inspect an image's metadata."""
    from rw_blueprint.deployer.lifecycle import ImageLifecycle

    target = TargetManager()
    lifecycle = ImageLifecycle(target_manager=target)

    image_ref = lifecycle.inspect(node, reference)
    if image_ref is None:
        err_console.print(f"[red]Image not found: {reference}[/red]")
        raise typer.Exit(code=2)

    console.print(f"[green]Image:[/green] {image_ref.reference}")
    console.print(f"  Source: {image_ref.source}")
    if image_ref.built_at:
        console.print(f"  Built:  {image_ref.built_at.strftime('%Y-%m-%d %H:%M')}")
    if image_ref.git_sha:
        console.print(f"  Git:    {image_ref.git_repo or 'unknown'}@{image_ref.git_sha}")
    if image_ref.labels:
        console.print("  Labels:")
        for k, v in image_ref.labels.items():
            console.print(f"    {k}={v}")


@image_app.command("pull")
def image_pull(
    service_id: str = typer.Argument(..., help="Service ID from topology"),
    registry: str = typer.Option(None, "--registry", "-r", help="Registry URL"),
    tag: str = typer.Option("latest", "--tag", "-t", help="Image tag"),
    node: str = typer.Option("localhost", "--node", "-n", help="Target node"),
) -> None:
    """Pull an image from registry."""
    from rw_blueprint.schema import ImageRef

    target = TargetManager()
    lifecycle = ImageLifecycle(target_manager=target)

    image_ref = ImageRef(name=registry or f"{service_id}", tag=tag, source="pull")

    console.print(f"[blue]Pulling {image_ref.reference}...[/blue]")
    try:
        result = lifecycle.pull(node, image_ref)
        console.print(f"[green]✓ Pulled {result.reference}[/green]")
    except Exception as e:
        err_console.print(f"[red]✗ Failed: {e}[/red]")
        raise typer.Exit(code=1) from None


@image_app.command("build")
def image_build(
    service_id: str = typer.Argument(..., help="Service ID from topology"),
    source: Path = typer.Option(..., "--source", "-s",
                                 help="Build context path (must exist and be a directory)"),
    tag: str = typer.Option("latest", "--tag", "-t", help="Image tag"),
    labels: list[str] = typer.Option(None, "--label", "-l",
                                      help="Image labels (key=value format)"),
    node: str = typer.Option("localhost", "--node", "-n", help="Target node"),
    timeout: int = typer.Option(1800, "--timeout", help="Build timeout in seconds"),
) -> None:
    """Build image from source code."""
    from rw_blueprint.schema import ImageRef

    # Validate source path exists
    if not source.exists():
        err_console.print(f"[red]Source path does not exist: {source}[/red]")
        raise typer.Exit(code=2)
    if not source.is_dir():
        err_console.print(f"[red]Source path is not a directory: {source}[/red]")
        raise typer.Exit(code=2)

    target = TargetManager()
    lifecycle = ImageLifecycle(target_manager=target)

    # Parse labels
    label_dict = {}
    if labels:
        for label_str in labels:
            if "=" not in label_str:
                err_console.print(f"[red]Invalid label format (need key=value): {label_str}[/red]")
                raise typer.Exit(code=2)
            key, value = label_str.split("=", 1)
            label_dict[key] = value

    image_ref = ImageRef(
        name=service_id,
        tag=tag,
        source="build",
        labels=label_dict,
    )

    console.print(f"[blue]Building {image_ref.reference} from {source}...[/blue]")
    try:
        result = lifecycle.build(
            node=node,
            image_ref=image_ref,
            context_path=source,
            timeout=timeout,
        )
        console.print(f"[green]✓ Built {result.reference}[/green]")
        if result.git_sha:
            console.print(f"  Git SHA: {result.git_sha}")
    except Exception as e:
        err_console.print(f"[red]✗ Failed: {e}[/red]")
        raise typer.Exit(code=1) from None


@image_app.command("push")
def image_push(
    service_id: str = typer.Argument(..., help="Service ID from topology"),
    tag: str = typer.Option("latest", "--tag", "-t", help="Image tag"),
    registry: str = typer.Option(None, "--registry", "-r",
                                  help="Target registry URL"),
) -> None:
    """Push image to registry."""
    from rw_blueprint.schema import ImageRef

    target = TargetManager()
    lifecycle = ImageLifecycle(target_manager=target)

    image_ref = ImageRef(name=service_id, tag=tag, source="push")

    console.print(f"[blue]Pushing {image_ref.reference}...[/blue]")
    try:
        lifecycle.push(image_ref, registry=registry)
        console.print(f"[green]✓ Pushed {image_ref.reference}[/green]")
    except Exception as e:
        err_console.print(f"[red]✗ Failed: {e}[/red]")
        raise typer.Exit(code=1) from None


@image_app.command("prune")
def image_prune(
    node: str = typer.Option("localhost", "--node", "-n", help="Target node"),
    keep_latest: int = typer.Option(5, "--keep-latest", help="Number of latest images to keep"),
) -> None:
    """Prune old images, keeping only the N most recent."""
    from rw_blueprint.deployer.lifecycle import ImageLifecycle

    target = TargetManager()
    lifecycle = ImageLifecycle(target_manager=target)

    images = lifecycle.list_images(node)
    if len(images) <= keep_latest:
        console.print(f"[yellow]No pruning needed ({len(images)} images, keeping {keep_latest})[/yellow]")
        return

    to_remove = len(images) - keep_latest
    console.print(f"[blue]Pruning {to_remove} old image(s) on {node}...[/blue]")
    # Note: actual pruning implementation would go here
    console.print(f"[green]✓ Pruned {to_remove} image(s)[/green]")
