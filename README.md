# rw_blueprint

Declarative YAML topology engine for RapidWebs infrastructure with drift detection, validation, and remediation.

## Features

- **Validate** — Check topology YAML against defined schema
- **Generate** — Produce Kubernetes manifests, docs, and configs from topology
- **Probe** — Run live infrastructure probes (ports, Incus, SSH)
- **Reconcile** — Detect drift between declared topology and live state
- **Remediate** — Propose and apply fixes for identified drift

## Quick Start

```bash
# Install
pip install -e ".[mcp]"

# Validate topology
rw-blueprint validate topology.yaml

# Generate artifacts
rw-blueprint generate topology.yaml --output docs/

# Run live probes
rw-blueprint probe --output live.json

# Reconcile drift
rw-blueprint reconcile topology.yaml live.json --format json
```

## RWDN Topology

Captures the full RapidWebs deployment network:
- 7 nodes (srv1, infra, enterprise, dev, workstation, cloudflare, domain)
- 11 services (honcho, postgres, inference, caddy, DNS, mail, storage)
- 13 links (Tailscale mesh, Cloudflare origin, DNS)
- 6 dependencies

## MCP Server

```bash
rw-blueprint-mcp
```

Provides 4 tools + 2 resources for topology management via Model Context Protocol.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for full design documentation.

## Testing

```bash
uv run pytest
# 80 tests passing
```
