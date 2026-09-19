# SPEC-005: Dependency-Aware Orchestration

**Status**: Implemented  
**Created**: 2026-09-15  
**Last Updated**: 2026-09-19  
**Parent**: SPEC-004 (Deployment Engine)

## 1. Problem Statement

Services have dependencies. Starting Caddy before Honcho will fail. Starting Honcho before Honcho-DB is insufficient. The deployment engine must understand and respect these relationships.

## 2. Goals

- [x] Parse dependency declarations from topology YAML
- [x] Build dependency graph (DAG)
- [x] Perform topological sort for startup order
- [x] Detect and reject circular dependencies
- [x] Wait for dependencies to be healthy before starting dependents
- [x] Handle partial failures gracefully

## 3. Design

### 3.1 Dependency Graph

```
Honcho-DB (postgres)
    ↑
Honcho-API (requires DB)
    ↑
┌───┴───┐
Caddy   Postfix
(requires  (requires
 API)      DNS)
    ↑
Portainer
```

### 3.2 Topological Sort Algorithm

Implemented in `src/rw_blueprint/deployer/graph.py`:

```python
def topological_sort(graph: DependencyGraph) -> list[list[str]]:
    """Sort services into startup layers using Kahn's algorithm."""
```

Returns list of layers where each layer can start in parallel.

### 3.3 Startup Phases

| Phase | Action | Example |
|-------|--------|---------|
| 1 | Start base services | Honcho-DB |
| 2 | Start dependent services | Honcho-API |
| 3 | Start proxy/gateway | Caddy, Portainer |
| 4 | Start edge services | Postfix, Dovecot |

### 3.4 Health Check Semantics

A service is "healthy" when:
1. `systemctl is-active` returns "active"
2. Optional: HTTP health endpoint returns 200
3. Optional: Custom health command succeeds

## 4. Implementation

### 4.1 Core Components

- `DependencyGraph` — DAG representation
- `build_dependency_graph()` — Construct from service list
- `topological_sort()` — Kahn's algorithm for ordering
- `detect_cycles()` — DFS-based cycle detection

### 4.2 Error Handling

- `CircularDependencyError` raised when cycles detected
- Partial failures logged but don't block other services
- Cross-node dependencies tracked via action dependencies

## 5. Test Coverage

| Test | Status |
|------|--------|
| Linear dependency order | ✅ |
| Parallel branches | ✅ |
| Circular dependency detection | ✅ |
| Missing dependency handling | ✅ |
| Cycle detection returns cycles | ✅ |

**Tests**: 194 passing

## 6. Usage Example

```bash
# Deploy with dependency ordering
rw-blueprint deploy topology.yaml --node infra

# Preview deployment plan
rw-blueprint plan topology.yaml --node infra
```

## 7. Future Enhancements

- [ ] Automatic wait for dependency health
- [ ] Retry failed dependencies
- [ ] Dependency health timeouts

---
