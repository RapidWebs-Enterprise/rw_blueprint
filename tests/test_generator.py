"""Tests for the generator pipeline."""

from __future__ import annotations

from datetime import date

from rw_blueprint.generator import (
    generate,
    render_incus_profiles,
    render_markdown,
    render_mermaid,
    render_quadlets,
)
from rw_blueprint.schema import Topology


def _topology() -> Topology:
    return Topology.model_validate(
        {
            "schema_version": "0.2",
            "metadata": {
                "name": "rapidwebs-rwdn",
                "description": "RapidWebs Distributed Network",
                "updated": date(2026, 8, 27),
            },
            "zones": [
                {"id": "edge", "name": "Edge"},
                {"id": "infra", "name": "Infra"},
            ],
            "nodes": [
                {"id": "cloudflare", "zone": "edge", "type": "external"},
                {
                    "id": "srv1",
                    "zone": "edge",
                    "type": "host",
                    "provider": "hetzner",
                    "public_ip": "89.167.54.98",
                    "tailscale_ip": "100.64.94.58",
                },
                {
                    "id": "infra",
                    "zone": "infra",
                    "type": "container",
                    "host": "srv1",
                    "tailscale_ip": "100.64.255.48",
                    "cpu": 2,
                    "memory": "2GiB",
                },
            ],
            "services": [
                {
                    "id": "pgvector",
                    "node": "infra",
                    "kind": "database",
                    "image": "docker.io/pgvector/pgvector:pg16",
                    "ports": [{"port": 5432}],
                    "managed_by": "quadlet",
                },
                {
                    "id": "honcho",
                    "node": "infra",
                    "kind": "application",
                    "image": "docker.io/rapidwebs/honcho:latest",
                    "ports": [{"port": 8000}],
                    "managed_by": "quadlet",
                },
            ],
            "dependencies": [
                {
                    "id": "honcho-requires-pgvector",
                    "from": "honcho",
                    "to": "pgvector",
                    "type": "requires",
                },
            ],
            "links": [
                {
                    "id": "cloudflare-to-srv1",
                    "from": "cloudflare",
                    "to": "srv1",
                    "protocol": "https",
                },
            ],
        }
    )


def test_render_mermaid_contains_nodes_and_links() -> None:
    out = render_mermaid(_topology())
    assert "cloudflare" in out
    assert "srv1" in out
    assert "infra" in out
    assert "cloudflare -->" in out


def test_render_markdown_contains_sections() -> None:
    out = render_markdown(_topology())
    assert "# rapidwebs-rwdn" in out
    assert "## Zones" in out
    assert "## Nodes" in out
    assert "## Services" in out
    assert "## Links" in out
    assert "## Dependencies" in out


def test_render_quadlets_only_managed_services() -> None:
    units = render_quadlets(_topology())
    assert set(units) == {"pgvector.container", "honcho.container"}
    assert "PublishPort=5432:5432" in units["pgvector.container"]
    assert "Requires=pgvector.service" in units["honcho.container"]


def test_render_quadlets_emits_image_no_placeholder() -> None:
    units = render_quadlets(_topology())
    assert "Image=docker.io/pgvector/pgvector:pg16" in units["pgvector.container"]
    assert "REPLACE_ME" not in units["pgvector.container"]
    assert "REPLACE_ME" not in units["honcho.container"]


def test_render_incus_profiles_only_containers() -> None:
    profiles = render_incus_profiles(_topology())
    assert set(profiles) == {"infra.profile.yaml"}
    assert "name: infra" in profiles["infra.profile.yaml"]


def test_render_incus_profiles_emits_resources() -> None:
    profiles = render_incus_profiles(_topology())
    assert 'limits.cpu: "2"' in profiles["infra.profile.yaml"]
    assert "limits.memory: 2GiB" in profiles["infra.profile.yaml"]


def test_generate_writes_expected_files(tmp_path) -> None:
    written = generate(_topology(), tmp_path)
    names = {p.name for p in written}
    assert "topology.mmd" in names
    assert "topology.md" in names
    assert "pgvector.container" in names
    assert "honcho.container" in names
    assert "infra.profile.yaml" in names


def test_generate_is_deterministic(tmp_path) -> None:
    topo = _topology()
    a = tmp_path / "a"
    b = tmp_path / "b"
    generate(topo, a)
    generate(topo, b)
    a_files = {p.relative_to(a): p.read_text() for p in a.rglob("*") if p.is_file()}
    b_files = {p.relative_to(b): p.read_text() for p in b.rglob("*") if p.is_file()}
    assert a_files == b_files


def test_generated_output_contains_no_secrets(tmp_path) -> None:
    """Generated output must not contain secret-like patterns (DOC-002)."""
    generate(_topology(), tmp_path)
    secret_markers = ("password", "secret", "api_key", "token=", "BEGIN PRIVATE KEY")
    for path in tmp_path.rglob("*"):
        if path.is_file():
            content = path.read_text().lower()
            for marker in secret_markers:
                assert marker not in content
