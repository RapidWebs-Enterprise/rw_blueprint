# Architecture

**Version:** 0.2.0  
**Last Updated:** 2026-09-19

---

## System Overview

rw_blueprint is a declarative infrastructure-as-code engine that treats `topology.yaml` as the single source of truth for the RapidWebs Distributed Network (RWDN). It validates topology definitions, generates deployment artifacts, probes live infrastructure, detects drift, and proposes remediation—all gated behind human-in-the-loop approval.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           rw_blueprint System                                │
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────────────┐  │
│  │   CLI       │    │  Generator  │    │         Deployer Engine         │  │
│  │  (Typer)    │───▶│  (Jinja2)   │───▶│  ┌─────────┐ ┌───────────────┐  │  │
│  └─────────────┘    └─────────────┘    │  │  Plan   │ │   Executor    │  │  │
│                                        │  └────┬────┘ └───────┬───────┘  │  │
│                                        │       │               │          │  │
│  ┌─────────────┐    ┌─────────────┐    │  ┌────┴────┐   ┌─────┴─────┐    │  │
│  │   Schema    │    │   Probes    │    │  │  Graph  │   │   Verify  │    │  │
│  │ (Pydantic)  │◄───│  (Registry) │    │  └─────────┘   └───────────┘    │  │
│  └─────────────┘    └─────────────┘    │                                  │  │
│                                        │  ┌──────────────────────────────┐  │  │
│  ┌─────────────┐    ┌─────────────┐    │  │     Reconciler & Drift       │  │  │
│  │  Rollback   │    │   State     │    │  │        Report                │  │  │
│  │  Executor   │◄───│   Tracker   │    │  └──────────────────────────────┘  │  │
│  └─────────────┘    └─────────────┘    │                                  │  │
│                                        │  ┌─────────────┐ ┌─────────────┐  │  │
│  ┌─────────────┐    ┌─────────────┐    │  │   Image     │ │    MCP      │  │  │
│  │  Security   │    │  Lifecycle  │    │  │  Lifecycle  │ │   Server    │  │  │
│  │  Module     │    │   Module    │    │  └─────────────┘ └─────────────┘  │  │
│  └─────────────┘    └─────────────┘    │                                  │  │
│                                        └──────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                              │
                                              ▼
                                    ┌─────────────────┐
                                    │  topology.yaml  │
                                    │  (Source of Truth)│
                                    └─────────────────┘
```

---

## Core Components

### 1. Schema Layer (`src/rw_blueprint/schema.py`)

**Purpose:** Type-safe topology validation using Pydantic v2

**Key Models:**
- `Topology` — Root document model
- `Node` — Infrastructure nodes (host, container, external)
- `Service` — Deployable workloads with image config
- `Link` — Connectivity between nodes
- `Dependency` — Service ordering constraints
- `ImageConfig` — Container image specifications

**Validation Features:**
- Strict schema enforcement (`extra="forbid"`)
- Cross-reference validation (zones, nodes, dependencies)
- Structured port parsing
- Service kind enumeration

### 2. Probe Registry (`src/rw_blueprint/probes/`)

**Purpose:** Read-only infrastructure observation

**Probes:**
| Probe | Source | Data Collected |
|-------|--------|----------------|
| `incus` | Incus CLI | Containers, profiles, storage pools |
| `podman` | Podman CLI | Running containers, images, volumes |
| `port` | Network sockets | Listening ports, processes |
| `dns` | DNS resolution | Name resolution, record validation |
| `tailscale` | Tailscale CLI | Mesh peers, IP assignments |

**Multi-Node Support:**
- SSH-based remote execution
- Parallel probe execution
- Result aggregation and normalization

### 3. Deployer Engine (`src/rw_blueprint/deployer/`)

**Purpose:** Execute deployment plans with safety guarantees

**Components:**
- **PlanGenerator** — Compare desired vs actual state
- **DependencyGraph** — DAG representation with topological sort
- **DeployExecutor** — SSH-based service deployment
- **HealthVerifier** — Post-deploy health checks
- **RollbackExecutor** — Automatic/manual rollback
- **DeploymentState** — JSON-based history tracking
- **ImageLifecycle** — Container image management

**Safety Features:**
- Dry-run mode (`--dry-run`)
- Confirmation prompts (`--force` to skip)
- Health check verification
- Auto-rollback on failure
- Partial failure handling (`continue_on_failure`)

### 4. Reconciler (`src/rw_blueprint/reconciler.py`)

**Purpose:** Three-way drift detection and classification

**Drift Types:**
- **Missing** — Declared in topology, absent in live state
- **Extra** — Present in live state, not in topology
- **Mismatched** — Present in both, but configuration differs

**Severity Tiers:**
- Critical — Service outage risk
- Warning — Potential inconsistency
- Info — Minor deviation

**Output Formats:**
- JSON (machine-readable)
- Markdown (human-readable)
- JSON Patch (remediation proposal)

### 5. Generator (`src/rw_blueprint/generator.py`)

**Purpose:** Produce deployment artifacts from topology

**Generated Artifacts:**
- Quadlet container units (`.container`)
- Incus profiles and launches
- Mermaid diagrams
- Markdown documentation
- JSON configuration

**Template System:**
- Jinja2 templating engine
- Custom filters and tests
- Extensible template library

### 6. Image Lifecycle (`src/rw_blueprint/deployer/lifecycle.py`)

**Purpose:** Manage container image operations

**Operations:**
- `inspect` — Query image metadata
- `pull` — Download from registry
- `build` — Build from source
- `push` — Upload to registry
- `tag` — Add version tags
- `prune` — Clean old images

**Security:**
- Path traversal protection
- Label sanitization
- Disk space validation
- Retry with exponential backoff

### 7. MCP Server (`src/rw_blueprint/mcp_server.py`)

**Purpose:** Agent integration via Model Context Protocol

**Tools:**
- `validate_topology` — Check YAML against schema
- `generate_artifacts` — Create deployment files
- `run_probes` — Collect live state
- `detect_drift` — Compare declared vs actual

**Resources:**
- `topology_schema` — JSON Schema for validation
- `drift_report` — Latest reconciliation result

---

## Data Flow

### Deployment Flow

```
1. User runs: rw-blueprint deploy topology.yaml --node infra
                │
                ▼
2. Load topology (schema validation)
                │
                ▼
3. Generate plan (desired vs actual comparison)
                │
                ▼
4. User confirms (unless --force or --dry-run)
                │
                ▼
5. Generate artifacts (Jinja2 templates)
                │
                ▼
6. Execute deployment (SSH to target node)
   ├─ Transfer quadlet files
   ├─ Reload systemd
   ├─ Start services
   └─ Record state
                │
                ▼
7. Verify health (systemctl + optional HTTP checks)
                │
                ├─ Success ──► Log deployment
                │
                └─ Failure ──► Auto-rollback
                                         │
                                         ▼
                                   Restore previous state
```

### Drift Detection Flow

```
1. User runs: rw-blueprint reconcile topology.yaml live.json
                │
                ▼
2. Load topology and live state
                │
                ▼
3. Normalize both to projection schema
                │
                ▼
4. Compare entity-by-entity
                │
                ▼
5. Classify drift
   ├─ Missing (in topology, not live)
   ├─ Extra (in live, not topology)
   └─ Mismatched (different attributes)
                │
                ▼
6. Generate drift report (JSON/Markdown)
                │
                ▼
7. Optionally generate JSON Patch remediation
```

---

## Configuration Layers

```
Priority (highest to lowest):
│
├── 1. CLI flags (--node, --force, etc.)
│
├── 2. Environment variables (RW_BLUEPRINT_*)
│
├── 3. User config (~/.rw_blueprint/config.yaml)
│
├── 4. Project config (config/defaults.yaml)
│
└── 5. Pydantic defaults (built-in values)
```

### Example User Config

```yaml
# ~/.rw_blueprint/config.yaml
ssh:
  default_user: sysop
  key_path: ~/.ssh/id_ed25519
  timeout: 30

probes:
  timeout: 30
  retry_count: 3
  parallel: true

deploy:
  continue_on_failure: true
  auto_rollback: true
  health_check_timeout: 60

images:
  build_timeout: 1800
  max_retries: 3
```

---

## Testing Strategy

### Test Categories

| Category | Files | Count | Coverage |
|----------|-------|-------|----------|
| Schema | `test_schema.py` | 19 | 100% |
| Graph | `test_graph.py` | 12 | 100% |
| Executor | `test_deploy_executor.py` | 35 | 95% |
| Lifecycle | `test_lifecycle.py` | 9 | 90% |
| Security | `test_lifecycle_security.py` | 17 | 100% |
| Integration | `test_integration.py` | 8 | 85% |
| Other | Various | 94+ | 90% |

**Total:** 194 tests, all passing

### Test Infrastructure

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/rw_blueprint --cov-report=term-missing

# Run specific category
uv run pytest tests/test_schema.py -v

# Run integration tests only
uv run pytest tests/test_integration.py -v
```

---

## CI/CD Pipeline

### GitHub Actions Workflow

```yaml
jobs:
  test:
    strategy:
      matrix:
        python-version: ['3.11', '3.12', '3.13']
    steps:
      - Checkout
      - Setup Python
      - Install uv
      - Run lint + format + types
      - Run tests with coverage
  
  build:
    steps:
      - uv build
      - Install wheel
      - Smoke test CLI commands
  
  security:
    steps:
      - pip-audit (vulnerability scan)
      - gitleaks (secret scan)
```

### Quality Gates

| Gate | Tool | Threshold |
|------|------|-----------|
| Linting | ruff | strict mode |
| Formatting | ruff format | line-length 100 |
| Type checking | mypy | strict |
| Tests | pytest | 100% pass rate |
| Coverage | pytest-cov | ≥ 80% |
| Security | pip-audit | 0 known vulns |
| Secrets | gitleaks | 0 secrets |

---

## Extension Points

### Custom Probes

```python
# src/rw_blueprint/probes/my_probe.py
from rw_blueprint.probes.base import BaseProbe

class MyProbe(BaseProbe):
    name = "my_probe"
    
    def collect(self, node: str, timeout: int = 30) -> dict:
        # Implement probe logic
        return {"data": "..."}
```

### Custom Generators

```python
# Extend template generation
from rw_blueprint.generator import BaseGenerator

class MyGenerator(BaseGenerator):
    def generate(self, topology, output_dir):
        # Generate custom artifacts
        pass
```

### Custom Health Checks

```python
# Add health check strategy
from rw_blueprint.deployer.verify import HealthCheckStrategy

class HttpHealthCheck(HealthCheckStrategy):
    def check(self, node: str, service: str) -> bool:
        # Implement HTTP health check
        pass
```

---

## Deployment Targets

### Supported Platforms

| Target | Type | Authentication | Notes |
|--------|------|----------------|-------|
| srv1 | Hetzner VM | SSH key | Production host |
| infra | Incus container | SSH key | Infrastructure services |
| enterprise | Incus container | SSH key | Enterprise apps |
| dev | Incus container | SSH key | Development |
| workstation | Local host | SSH key | Development |

### Network Topology

```
                    ┌─────────────┐
                    │  Cloudflare │
                    │   (edge)    │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  srv1       │
                    │  (Hetzner)  │
                    └──┬───┬───┬──┘
                       │   │   │
              ┌────────┘   │   └────────┐
              ▼            ▼            ▼
       ┌──────────┐ ┌──────────┐ ┌──────────┐
       │  infra   │ │enterprise│ │   dev    │
       │(Incus)   │ │(Incus)   │ │(Incus)   │
       └──────────┘ └──────────┘ └──────────┘
```

---

## Security Model

### Principle: Emit Untrusted, Apply Gated

```
┌─────────────────────────────────────────────────────────────┐
│                    Security Boundary                         │
│                                                             │
│  ┌─────────────┐      ┌─────────────┐      ┌───────────┐  │
│  │   Probes    │ ───▶ │ Reconciler  │ ───▶ │  Drift    │  │
│  │  (untrusted)│      │   (analyzes)│      │  Report   │  │
│  └─────────────┘      └─────────────┘      └─────┬─────┘  │
│                                                   │        │
│                                            ┌──────▼──────┐  │
│                                            │  HITL Gate  │  │
│                                            │ (approval)  │  │
│                                            └──────┬──────┘  │
│                                                   │        │
│                                            ┌──────▼──────┐  │
│                                            │  Apply      │  │
│                                            │ (gated)     │  │
│                                            └─────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Security Features

| Feature | Implementation |
|---------|----------------|
| Path traversal protection | Validate build context against allowed roots |
| Label sanitization | Regex validation: `^[a-zA-Z0-9_.\-]+$` |
| Disk space checks | Pre-build validation on target node |
| SSH hardening | Key-based auth, timeout limits |
| Input validation | Pydantic strict mode, schema enforcement |
| Secret handling | Never log credentials, use env vars |

---

## Future Roadmap

### Phase 1 (Current)
- ✅ Core topology engine
- ✅ Multi-node probing
- ✅ Drift detection
- ✅ Deployment engine
- ✅ Image lifecycle

### Phase 2 (Planned)
- [ ] Watchdog push architecture
- [ ] Secrets management integration
- [ ] Progressive delivery (canary, blue-green)
- [ ] Multi-cloud provider support
- [ ] Web UI for topology management

### Phase 3 (Future)
- [ ] Autonomous self-healing agent
- [ ] Predictive drift detection
- [ ] Cost optimization recommendations
- [ ] Compliance auditing

---

**Document Version:** 1.0  
**Last Updated:** 2026-09-19  
**Maintained by:** RapidWebs Infrastructure Team
