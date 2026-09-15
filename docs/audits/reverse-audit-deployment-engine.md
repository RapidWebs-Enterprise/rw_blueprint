# Reverse Audit: SPEC-004/005/006 + ADR-019/020

**Auditor**: Reverse Audit Subagent  
**Date**: 2026-09-15  
**Target**: What's missing from the deployment engine design?

## Missing Components

### 1. Configuration Management

**Gap**: No spec for how secrets/configs are injected into services.

**Current State**:
- Quadlet supports `EnvironmentFile=` and `Secret=` directives
- topology.yaml has no mechanism to declare environment variables
- No mention of Vault, SOPS, or git-crypt integration

**Risk**: High — services like postgres, honcho need database passwords, API keys.

**Recommendation**: Add to SPEC-004 Section 4.x:
```yaml
services:
  - id: honcho-api
    environment:
      DATABASE_URL: env:postgres-conn-string  # Reference to secret store
      API_KEY: file:/etc/secrets/honcho-api-key
```

### 2. Network Configuration

**Gap**: No spec for Podman networks, port publishing, or Caddy reverse proxy configuration.

**Current State**:
- Quadlet supports `.network` files
- Caddy is mentioned as dependency but no auto-configuration
- No spec for how `*.rapidwebs.org` routes to services

**Risk**: Medium — networking is critical for multi-service deployments.

**Recommendation**: Add network section to topology.yaml:
```yaml
networks:
  - id: internal
    driver: bridge
    services: [honcho-api, honcho-db]
  - id: external
    driver: bridge
    services: [caddy]
```

### 3. Storage Management

**Gap**: No spec for volume management, backups, or data persistence.

**Current State**:
- Quadlet supports `Volume=` directive
- No mention of backup strategies for postgres, SeaweedFS
- No spec for volume lifecycle (create, migrate, destroy)

**Risk**: Medium — data loss risk if volumes aren't managed.

**Recommendation**: Add storage section to topology.yaml:
```yaml
volumes:
  - id: postgres-data
    driver: local
    service: honcho-db
    backup:
      enabled: true
      schedule: "0 2 * * *"
```

### 4. Error Handling & Retry Logic

**Gap**: No spec for deployment failure handling, retry policies, or timeout configuration.

**Current State**:
- SPEC mentions "rollback on failure" but not retry strategy
- No exponential backoff described
- No spec for partial deployment scenarios

**Risk**: High — network blips will cause deployment failures without retry.

**Recommendation**: Add to SPEC-004 Section 4.2:
```yaml
deployment:
  retry:
    max_attempts: 3
    backoff: exponential
    initial_delay: 5s
    max_delay: 60s
  timeout:
    service_start: 120s
    health_check: 30s
```

### 5. Logging & Observability

**Gap**: No spec for log collection, metrics, or integration with existing observability stack.

**Current State**:
- `journalctl` available for systemd services
- No spec for log aggregation (Loki, ELK)
- No spec for metrics export (Prometheus)

**Risk**: Low-Medium — operational visibility gap.

**Recommendation**: Phase 2 item, but note in spec:
```yaml
services:
  - id: honcho-api
    logging:
      driver: journald
      metrics:
        enabled: true
        endpoint: http://localhost:9100/metrics
```

### 6. Multi-Node Coordination

**Gap**: SPEC-004 explicitly lists "Multi-node coordinated deployments" as Non-Goal (Phase 2), but no migration path is described.

**Current State**:
- Current implementation targets single node
- No spec for cross-node dependencies (e.g., Caddy on infra → App on enterprise)

**Risk**: Medium — will hit this limitation quickly.

**Recommendation**: Add "Future Work" section to ADR-019:
```markdown
## Future Work
- Cross-node dependency resolution
- Distributed deployment orchestration
- Consensus-based state reconciliation
```

### 7. Testing Strategy

**Gap**: No spec for testing deployment engine itself.

**Current State**:
- Unit tests mentioned in SPEC-004 Section 7
- No integration test strategy
- No test environment specification

**Risk**: Medium — deploying without testing is risky.

**Recommendation**: Add to SPEC-004 Section 7:
```markdown
## Testing Strategy

### Unit Tests
- Topological sort algorithm
- Rollback logic
- Dependency graph construction

### Integration Tests
- Deploy single service to test VM
- Deploy with dependencies
- Rollback on failure simulation

### Test Environment
- Use existing `dev` Incus VM
- Isolated from production infrastructure
```

## Critical Missing Items Summary

| # | Missing Component | Severity | Effort to Add |
|---|-------------------|----------|---------------|
| 1 | Configuration/Secrets Management | 🔴 High | 2-3 days |
| 2 | Network Configuration | 🟠 Medium | 1-2 days |
| 3 | Storage Management | 🟠 Medium | 1 day |
| 4 | Error Handling & Retry | 🔴 High | 1 day |
| 5 | Logging & Observability | 🟡 Low | 2 days (Phase 2) |
| 6 | Multi-Node Coordination | 🟠 Medium | 3-5 days (Phase 2) |
| 7 | Testing Strategy | 🟠 Medium | 1 day |

## Recommendation

**Do not proceed with implementation until items 1-4 are added to the spec.** These are blocking requirements for production use.

Items 5-7 can be deferred to Phase 2 with clear migration path documented.
