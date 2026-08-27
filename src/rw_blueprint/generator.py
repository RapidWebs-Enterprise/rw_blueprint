"""Generator pipeline: validated model -> derived artifacts.

The generator is a thin renderer over the validated :class:`Topology` model.
It emits three artifact families from the single source of truth:

* Mermaid topology diagram (human-facing)
* Markdown documentation (human-facing)
* IaC skeletons -- podman quadlet units and Incus profiles (machine-facing)

All output is deterministic: identical input produces byte-identical output
(REQ-007). Templates live under ``src/rw_blueprint/templates/`` and contain
presentation logic only (ADR-004).
"""

from __future__ import annotations

from pathlib import Path

import yaml
from jinja2 import Environment, PackageLoader, StrictUndefined

from rw_blueprint.schema import Node, Service, Topology


def load_topology(path: str | Path) -> Topology:
    """Load and validate a topology YAML file.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        yaml.YAMLError: If the file is not valid YAML.
        ValueError: If the file is empty or violates the schema.
    """
    raw = yaml.safe_load(Path(path).read_text())
    if raw is None:
        raise ValueError(f"topology file '{path}' is empty")
    return Topology.model_validate(raw)


def _environment() -> Environment:
    """Build a strict, deterministic Jinja2 environment."""
    return Environment(
        loader=PackageLoader("rw_blueprint", "templates"),
        # Output is Mermaid/markdown/quadlet text, never HTML; autoescaping
        # would corrupt the generated artifacts.
        autoescape=False,  # noqa: S701
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )


def _zones_with_nodes(topology: Topology) -> list[dict[str, object]]:
    """Group nodes by zone, preserving zone and node declaration order."""
    nodes_by_zone: dict[str, list[Node]] = {}
    for node in topology.nodes:
        nodes_by_zone.setdefault(node.zone, []).append(node)
    return [{"zone": zone, "nodes": nodes_by_zone.get(zone.id, [])} for zone in topology.zones]


def _dependencies_of(topology: Topology, service: Service) -> list[str]:
    """Return the ids of services ``service`` depends on (via ``requires`` edges)."""
    return [
        dep.to
        for dep in topology.dependencies
        if dep.from_ == service.id and dep.type == "requires"
    ]


def render_mermaid(topology: Topology) -> str:
    """Render the Mermaid topology diagram."""
    template = _environment().get_template("topology.mmd.j2")
    return template.render(topology=topology, zones_with_nodes=_zones_with_nodes(topology))


def render_markdown(topology: Topology) -> str:
    """Render the Markdown documentation."""
    template = _environment().get_template("topology.md.j2")
    service_deps = {s.id: _dependencies_of(topology, s) for s in topology.services}
    return template.render(topology=topology, service_deps=service_deps)


def render_quadlets(topology: Topology) -> dict[str, str]:
    """Render quadlet units for services managed by quadlet.

    Returns a mapping of ``{unit_filename: content}``.
    """
    template = _environment().get_template("quadlet.container.j2")
    result: dict[str, str] = {}
    for service in topology.services:
        if service.managed_by == "quadlet":
            result[f"{service.id}.container"] = template.render(
                service=service,
                depends_on=_dependencies_of(topology, service),
            )
    return result


def render_incus_profiles(topology: Topology) -> dict[str, str]:
    """Render Incus profiles for container nodes.

    Returns a mapping of ``{profile_filename: content}``.
    """
    template = _environment().get_template("incus.profile.j2")
    result: dict[str, str] = {}
    for node in topology.nodes:
        if node.type == "container":
            result[f"{node.id}.profile.yaml"] = template.render(node=node)
    return result


def generate(topology: Topology, output_dir: str | Path) -> list[Path]:
    """Write all derived artifacts to ``output_dir`` and return written paths."""
    out = Path(output_dir)

    def _write(relative: str, content: str) -> Path:
        path = out / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    written: list[Path] = []
    written.append(_write("topology.mmd", render_mermaid(topology)))
    written.append(_write("topology.md", render_markdown(topology)))
    for name, content in render_quadlets(topology).items():
        written.append(_write(f"quadlet/{name}", content))
    for name, content in render_incus_profiles(topology).items():
        written.append(_write(f"incus/{name}", content))
    return written
