# SPEC-005: Dependency-Aware Orchestration

**Status**: Proposed  
**Created**: 2026-09-15  
**Parent**: SPEC-004 (Deployment Engine)

## 1. Problem Statement

Services have dependencies. Starting Caddy before Honcho will fail. Starting Honcho before Honcho-DB is insufficient. The deployment engine must understand and respect these relationships.

## 2. Goals

- [ ] Parse dependency declarations from topology YAML
- [ ] Build dependency graph (DAG)
- [ ] Perform topological sort for startup order
- [ ] Detect and reject circular dependencies
- [ ] Wait for dependencies to be healthy before starting dependents
- [ ] Handle partial failures gracefully

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

```python
def topological_sort(services: list[Service]) -> list[list[Service]]:
    """Sort services into startup layers.
    
    Returns list of layers, where each layer can start in parallel.
    """
    graph = build_dependency_graph(services)
    in_degree = {s.id: len(graph[s.id].depends_on) for s in services}
    queue = [s for s in services if in_degree[s.id] == 0]
    layers = []
    
    while queue:
        layer = queue.copy()
        queue = []
        for service in layer:
            layers.append(service)
            for dependent in graph[service.id].dependents:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
    
    if len(layers) != len(services):
        raise CircularDependencyError("Circular dependency detected")
    
    return layers
```

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

```yaml
services:
  - id: honcho-api
    health_check:
      http:
        url: http://localhost:8000/health
        expected_status: 200
      timeout: 30
```

## 4. Failure Handling

### 4.1 Dependency Not Ready

If service A depends on B, and B fails to start:
- Wait for configured timeout
- If still failed, abort deployment of A
- Roll back any partially deployed services

### 4.2 Partial Failure

If some services succeed and others fail:
- Stop all successfully started services
- Log the failure state
- Require manual intervention

## 5. Testing Requirements

- [ ] Test topological sort with linear dependency
- [ ] Test topological sort with parallel branches
- [ ] Test circular dependency detection
- [ ] Test missing dependency handling
- [ ] Test health check timeout
- [ ] Test rollback on dependency failure

## 6. Open Questions

- [ ] Should we support soft dependencies (Wants=) vs hard dependencies (Requires=)?
- [ ] How to handle dynamic dependencies (service discovery)?
