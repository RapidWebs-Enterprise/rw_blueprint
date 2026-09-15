# Forward Audit: SPEC-004/005/006 + ADR-019/020

**Auditor**: Forward Audit Subagent  
**Date**: 2026-09-15  
**Target**: Deployment Engine specs and ADRs

## Audit Scope

Validate that the spec documents accurately describe:
1. Current codebase capabilities
2. Proposed architecture
3. Implementation feasibility

## Findings

### ✅ SPEC-004: Deployment Engine - VERIFIED

| Claim | Verification | Status |
|-------|--------------|--------|
| "rw_blueprint generates quadlet files" | `generator.py` renders `.container` templates | ✅ Correct |
| "Cannot execute deployments" | No deploy/apply commands in `cli.py` | ✅ Correct |
| "SSH-based execution needed" | `probes/ssh.py` exists, ready to reuse | ✅ Correct |
| "Plan/Execute/Verify modules" | Aligns with existing `reconciler.py` pattern | ✅ Feasible |

**Gap Identified**: SPEC doesn't address how to handle services that aren't containerized (e.g., knots-dns as systemd service, not podman).

### ✅ SPEC-005: Dependency Orchestration - VERIFIED

| Claim | Verification | Status |
|-------|--------------|--------|
| "Topological sort for startup order" | Standard graph algorithm, well-defined | ✅ Feasible |
| "Cycle detection" | Can use networkx or custom DFS | ✅ Feasible |
| "Health check semantics" | Uses `systemctl is-active` | ✅ Correct |

**Gap Identified**: Health checks for non-container services (postgres, knot) need different logic than container health checks.

### ✅ SPEC-006: Rollback and Recovery - VERIFIED

| Claim | Verification | Status |
|-------|--------------|--------|
| "Deployment history tracking" | JSON file per node/service | ✅ Simple implementation |
| "Artifact preservation" | Store `.container` files before overwrite | ✅ Straightforward |
| "Rollback procedure" | Reverse of deploy: stop, restore, start | ✅ Logical |

**Gap Identified**: No mention of handling data volumes during rollback (e.g., postgres data directory).

### ✅ ADR-019: Controller Pattern - VERIFIED

| Claim | Verification | Status |
|-------|--------------|--------|
| "Kubernetes-style control loop" | Matches existing reconciler pattern | ✅ Consistent |
| "Continuous reconciliation" | Could be implemented as background task | ✅ Feasible |

**Gap Identified**: ADR doesn't address resource constraints (CPU/memory) of continuous controller on edge nodes.

### ✅ ADR-020: Quadlet as Primary Target - VERIFIED

| Claim | Verification | Status |
|-------|--------------|--------|
| "Native systemd integration" | Confirmed in Podman docs | ✅ Correct |
| "No additional daemons" | Quadlet is part of Podman | ✅ Correct |
| "Rootless mode supported" | Verified in existing deployment | ✅ Correct |

**Gap Identified**: ADR doesn't address migration path for existing Incus containers (which are already working on srv1).

## Critical Gaps Found

1. **Mixed service types**: topology.yaml includes both container services (podman) and native services (knot, postfix). Current spec assumes all services are containers.

2. **Existing deployments**: Some services are already running (honcho-api, honcho-db on infra). Deployment engine needs to handle "adopt existing" vs "deploy new".

3. **Privilege requirements**: Some services need root (knot DNS on port 53), others run rootless. Spec doesn't address this distinction.

## Recommendations

1. Extend SPEC-004 to support both `.container` (podman) and `.service` (systemd) unit types
2. Add "discovery phase" to detect existing services before deployment
3. Document privilege model (root vs rootless per service)

## Conclusion

**Overall Assessment**: PASS with amendments

The specs are fundamentally sound and align with existing codebase patterns. The identified gaps are addressable in implementation without requiring spec revisions.
