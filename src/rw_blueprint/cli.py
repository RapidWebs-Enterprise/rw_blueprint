"""Command-line interface for rw_blueprint."""

from __future__ import annotations

import typer
from rich.console import Console

from rw_blueprint.generator import generate as generate_artifacts
from rw_blueprint.generator import load_topology

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


if __name__ == "__main__":
    app()
