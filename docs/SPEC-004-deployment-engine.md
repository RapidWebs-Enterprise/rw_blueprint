# SPEC-004: Deployment Engine

**Status**: Proposed  
**Created**: 2026-09-15  
**Owner**: RapidWebs Infrastructure Team

## 1. Problem Statement

rw_blueprint currently generates deployment artifacts (quadlet containers, Incus profiles) but cannot **execute** them. The gap between YAML declaration and actual running services requires manual intervention:

```bash
# Current workflow (manual):
rw-blueprint generate topology.yaml docs/generated/
scp *.container infra:/etc/containers/systemd/
ssh infra "sudo systemctl daemon-reload && sudo systemctl enable --now caddy.container"
```

This is error-prone, unrepeatable, and lacks:
- Dependency ordering (Caddy must start after Honcho)
- Health checks (verify service is ready)
- Rollback capability (revert if deployment fails)
- State tracking (what's deployed, when, by whom)

## 2. Goals

- [x] Deploy services from `topology.yaml` to target nodes via SSH
- [x] Respect dependency ordering declared in topology
- [x] Verify service health after deployment
- [x] Support rollback on failure
- [x] Track deployment history
- [x] Support dry-run mode (preview changes without applying)

## 3. Non-Goals

- [ ] Multi-node coordinated deployments (Phase 2)
- [ ] Progressive delivery (canary, blue-green)
- [ ] Secrets management integration
- [ ] Cloud provider APIs

## 4. Design

### 4.1 Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Deployment Engine                         │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Plan      │  │   Execute   │  │   Verify            │  │
│  │   Module    │  │   Module    │  │   Module            │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         │                │                     │             │
│         └────────────────┴─────────────────────┘             │
│                              │                               │
│              ┌───────────────┴───────────────┐               │
│              │        Target Manager          │               │
│              │  (SSH connections to nodes)    │               │
│              └───────────────────────────────┘               │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Module Responsibilities

**Plan Module**
- Compare desired state (topology) with actual state (probes)
- Generate deployment plan: what to create/update/delete
- Estimate blast radius and dependencies
- Output plan in JSON format for review

**Execute Module**
- Transfer quadlet files to target node via SSH
- Run `systemctl daemon-reload`
- Start services in dependency order (topological sort)
- Log each operation with timestamps

**Verify Module**
- Check service health via `systemctl is-active`
- Poll health endpoint if configured
- Mark deployment as "healthy" or "failed"

### 4.3 Dependency Ordering

Services declare dependencies via `depends_on` in topology:

```yaml
services:
  - id: caddy
    kind: reverse_proxy
    depends_on:
      - honcho-api
      - knots-dns
```

The engine performs topological sort to determine startup order:
1. Services with no dependencies → start first
2. Services wait for dependencies to be healthy
3. Cycles detected → abort with error

### 4.4 Rollback Strategy

On failure:
1. Stop new service(s)
2. Restart previous healthy version (if exists)
3. If no previous version, leave in failed state for manual intervention
4. Log rollback actions

## 5. CLI Interface

```bash
# Preview changes without applying
rw-blueprint plan topology.yaml --nodes infra,enterprise

# Apply deployment plan
rw-blueprint apply topology.yaml --nodes infra --dry-run=false

# Rollback last deployment
rw-blueprint rollback --node infra --service caddy

# Check deployment status
rw-blueprint status --node infra
```

## 6. Configuration

```yaml
# config.yaml
deployment:
  default_timeout: 120  # seconds
  max_parallel: 3       # concurrent deployments per node
  health_check:
    interval: 5         # seconds between checks
    timeout: 30         # max wait for healthy
    retries: 3
  rollback:
    enabled: true
    auto: false         # require approval for production
```

## 7. Testing Requirements

- [ ] Unit tests for topological sort algorithm
- [ ] Unit tests for rollback logic
- [ ] Integration test: deploy single service to infra
- [ ] Integration test: deploy with dependencies
- [ ] Integration test: rollback on failure
- [ ] Dry-run mode verification
- [ ] SSH connection failure handling

## 8. Open Questions

- [ ] How to handle secrets injection?
- [ ] Should we use existing tools (kuadrat, ansible) or build custom?
- [ ] What's the minimum viable deployment target?

## 9. References

- [Kuadrat](https://github.com/rifkyputra/kuadrat) — Podman Quadlet deployment daemon
- [Kubernetes Controllers](https://kubernetes.io/docs/concepts/architecture/controller/)
- [GitOps with ArgoCD/Flux](https://argo-cd.readthedocs.io/)
