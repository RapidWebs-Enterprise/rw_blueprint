# rw_blueprint

**Declarative YAML topology engine with drift detection and remediation.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://github.com/RapidWebs-Enterprise/rw_blueprint/actions/workflows/test.yml/badge.svg)](https://github.com/RapidWebs-Enterprise/rw_blueprint/actions)
[![PyPI version](https://img.shields.io/pypi/v/rw-blueprint.svg)](https://pypi.org/project/rw-blueprint/)

---

## Overview

`rw_blueprint` is a declarative infrastructure-as-code engine that treats `topology.yaml` as the single source of truth for the RapidWebs Distributed Network (RWDN). It validates topology definitions, generates deployment artifacts (quadlet units, Incus profiles), probes live infrastructure state, detects drift between declared and actual configurations, and proposes remediation plans—all gated behind human-in-the-loop approval.

### Key Features

| Feature | Description |
|---------|-------------|
| **Validate** | Schema validation with strict type checking |
| **Generate** | Produce quadlet containers, Incus profiles, documentation |
| **Probe** | Collect live state from multiple infrastructure sources |
| **Reconcile** | Three-way drift classification (missing/extra/mismatched) |
| **Deploy** | Execute deployment plans with dependency ordering |
| **Image Lifecycle** | Build, pull, push, inspect container images |
| **Rollback** | Automatic/manual rollback on health check failure |
| **MCP Integration** | Agent integration via Model Context Protocol |

---

## Quick Start

```bash
# Install
pip install -e ".[mcp]"

# Validate topology
rw-blueprint validate topology.yaml

# Generate deployment artifacts
rw-blueprint generate topology.yaml --output docs/generated/

# Run live infrastructure probes
rw-blueprint probe --nodes srv1,infra,enterprise,dev --output docs/live.json

# Detect drift
rw-blueprint reconcile topology.yaml docs/live.json

# Preview deployment
rw-blueprint plan topology.yaml --node infra --dry-run

# Deploy with auto-rollback on failure
rw-blueprint deploy topology.yaml --node infra

# Rollback a service
rw-blueprint rollback honcho-api --node infra
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        rw_blueprint                                 │
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐ │
│  │   CLI       │  │  Generator  │  │      Deployer Engine        │ │
│  │   (Typer)   │  │   (Jinja2)  │  │  ┌─────────┐ ┌───────────┐  │ │
│  └──────┬──────┘  └──────┬──────┘  │  │  Plan   │ │  Executor │  │ │
│         │                │         │  └────┬────┘ └─────┬─────┘  │ │
│        ┌┴┐              ┌┴┐        │       │           │         │ │
│        │ │              │ │        │  ┌────┴────┐ ┌────┴─────┐   │ │
│        │ │              │ │        │  │  Probe  │ │  Verify   │   │ │
│        │ │              │ │        │  │ Registry│ │  Health   │   │ │
│        │ │              │ │        │  └────┬────┘ └──────────┘   │ │
│        └┬┘              └┬┘        │       │                      │ │
│  ┌──────┴────────────────┴──────┐   │  ┌───┴────┐                 │ │
│  │     Schema & Topology        │   │  │ Image  │                 │ │
│  │  (Pydantic v2 + YAML)        │   │  │Lifecycle│                 │ │
│  └──────────────────────────────┘   │  └────────┘                 │ │
│                                    │                             │ │
│  ┌────────────────────────────────┴───────────────────────────┐  │ │
│  │                  Reconciler & Drift Report                  │  │ │
│  │         (Three-way: missing / extra / mismatched)          │  │ │
│  └────────────────────────────────────────────────────────────┘  │ │
│                                                                  │ │
│  ┌─────────────┐  ┌─────────────┐  ┌───────────────────────────┐ │
│  │   Rollback  │  │   State     │  │        MCP Server         │ │
│  │  Executor   │  │  Tracker    │  │  (4 tools + 2 resources)  │ │
│  └─────────────┘  └─────────────┘  └───────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## RWDN Topology

Captures the full RapidWebs Distributed Network:

- **7 nodes**: srv1, infra, enterprise, dev, workstation, cloudflare, domain
- **11 services**: honcho, postgres, inference, caddy, DNS, mail, storage, postmap, portainer, etc.
- **13 links**: Tailscale mesh, Cloudflare origin, DNS
- **6 dependencies**: Service ordering constraints

See [`topology.yaml`](topology.yaml) for the complete declaration.

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `validate <path>` | Validate topology YAML against schema |
| `generate <topology> <output>` | Generate docs, diagrams, IaC from topology |
| `probe [options]` | Run live infrastructure probes |
| `reconcile <topology> <live>` | Diff declared vs observed state |
| `plan <topology> [options]` | Generate deployment plan |
| `deploy <topology> [options]` | Execute deployment to node |
| `rollback <service> [options]` | Rollback service to previous version |
| `image [subcommand]` | Manage container image lifecycle |
| `mcp` | Start MCP server for agent integration |

### Probe Subcommands

```bash
rw-blueprint probe --nodes srv1,infra,enterprise,dev
rw-blueprint probe --probes incus,podman,port,tailscale,dns
rw-blueprint probe --output docs/live-all.json
```

### Deploy Options

```bash
# Deploy with dry-run preview
rw-blueprint deploy topology.yaml --node infra --dry-run

# Deploy specific services
rw-blueprint deploy topology.yaml --node infra --services honcho-api,caddy

# Force deploy (skip confirmation + auto-rollback)
rw-blueprint deploy topology.yaml --node infra --force
```

### Image Commands

```bash
rw-blueprint image list --node infra
rw-blueprint image inspect honcho:latest --node infra
rw-blueprint image build honcho-api --source /home/sysop/honcho --node infra
rw-blueprint image pull honcho:latest --registry ghcr.io
rw-blueprint image push honcho:latest --registry ghcr.io
rw-blueprint image prune --node infra --keep-latest 5
```

---

## Configuration

Layered configuration (highest priority first):

1. **CLI flags** — `--node`, `--force`, etc.
2. **Environment variables** — `RW_BLUEPRINT_` prefix
3. **User config** — `~/.rw_blueprint/config.yaml`
4. **Project config** — `config/defaults.yaml`
5. **Pydantic defaults** — Built-in values

### Example User Config

```yaml
# ~/.rw_blueprint/config.yaml
ssh:
  default_user: sysop
  key_path: ~/.ssh/id_ed25519

probes:
  timeout: 30
  retry_count: 3

deploy:
  continue_on_failure: true
  auto_rollback: true
```

---

## Testing

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/rw_blueprint --cov-report=term-missing

# Run specific test file
uv run pytest tests/test_schema.py -v

# Current status: 194 tests passing
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Full system architecture |
| [docs/SPEC-004.md](docs/SPEC-004-deployment-engine.md) | Deployment engine spec |
| [docs/SPEC-005.md](docs/SPEC-005-dependency-orchestration.md) | Dependency orchestration |
| [docs/SPEC-006.md](docs/SPEC-006-rollback-recovery.md) | Rollback and recovery |
| [docs/specs/image-lifecycle.md](docs/specs/image-lifecycle.md) | Image lifecycle spec |
| [docs/adr-*/](docs/adrs/) | Architecture Decision Records |
| [docs/audits/*.md](docs/audits/) | Audit reports |
| [OPERATOR_GUIDE.md](docs/operator-guide/image-lifecycle.md) | Operator documentation |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

### Development Setup

```bash
# Clone
git clone https://github.com/RapidWebs-Enterprise/rw_blueprint.git
cd rw_blueprint

# Create virtual environment
uv venv --python 3.11
source .venv/bin/activate

# Install dependencies
uv pip install -e ".[dev,mcp]"

# Run tests
uv run pytest
```

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Support

- **Issues**: [GitHub Issues](https://github.com/RapidWebs-Enterprise/rw_blueprint/issues)
- **Security**: See [SECURITY.md](SECURITY.md)
- **Documentation**: [docs/](docs/) directory

---

**Version:** 0.2.0  
**Last Updated:** 2026-09-19  
**Status:** Production-ready
