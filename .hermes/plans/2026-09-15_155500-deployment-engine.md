# Implementation Plan: Deployment Engine (Medium Mode)

**Date**: 2026-09-15  
**Mode**: MEDIUM (5+ files, reusable feature, requires TDD + audits)  
**Estimate**: 3-4 days (24-32 hours)

## Audit Summary

### Forward Audit: PASS ✅
- Verified specs align with existing codebase
- Confirmed `generator.py` produces valid quadlet files
- Validated SSH module (`probes/ssh.py`) is reusable
- Identified 3 gaps (mixed service types, existing deployments, privileges)

### Reverse Audit: PASS ⚠️
- Found 7 missing components
- **Blocking**: Configuration management, error handling, retry logic
- **Deferrable**: Multi-node coordination, observability (Phase 2)

### Audit Findings Incorporated
1. Added `config_management` section to SPEC-004
2. Added `error_handling` and `retry` subsections to SPEC-004
3. Added `service_types` clarification (container vs systemd)
4. Added testing strategy section

---

## Phase 1: Core Infrastructure (1 day)

### Task 1.1: Extension Point for Service Types
**File**: `src/rw_blueprint/schema.py`  
**Effort**: 2h  
**Description**: Add `ServiceType` enum and extend `Service` model to support both container and systemd service types.

```python
class ServiceType(str, Enum):
    CONTAINER = "container"  # Podman Quadlet
    SYSTEMD = "systemd"      # Native systemd service

class Service(BaseModel):
    # ... existing fields ...
    service_type: ServiceType = ServiceType.CONTAINER
    privileged: bool = False  # Root vs rootless
```

**Tests**: `tests/test_schema_service_types.py`

---

### Task 1.2: Dependency Graph Module
**File**: `src/rw_blueprint/deployer/graph.py`  
**Effort**: 3h  
**Description**: Implement topological sort with cycle detection.

```python
def build_dependency_graph(services: list[Service]) -> DependencyGraph:
    """Build DAG from service dependencies."""
    ...

def topological_sort(graph: DependencyGraph) -> list[list[Service]]:
    """Sort services into startup layers."""
    ...

def detect_cycles(graph: DependencyGraph) -> list[str]:
    """Return list of cycles if any."""
    ...
```

**Tests**: `tests/test_dependency_graph.py`

---

### Task 1.3: Deployment Plan Generator
**File**: `src/rw_blueprint/deployer/plan.py`  
**Effort**: 3h  
**Description**: Compare desired state (topology) with actual state (probes) to generate deployment plan.

```python
@dataclass
class DeploymentPlan:
    actions: list[DeploymentAction]
    estimated_duration: timedelta
    blast_radius: BlastRadius

class PlanGenerator:
    def generate(self, topology: Topology, live: LiveState) -> DeploymentPlan:
        ...
```

**Tests**: `tests/test_deployment_plan.py`

---

## Phase 2: Execution Engine (1 day)

### Task 2.1: Target Manager (SSH)
**File**: `src/rw_blueprint/deployer/targets.py`  
**Effort**: 4h  
**Description**: Manage SSH connections to target nodes, reuse existing `probes/ssh.py`.

```python
class TargetManager:
    def __init__(self, nodes: dict[str, NodeConfig]):
        self.nodes = nodes
    
    def execute(self, node_id: str, command: list[str], timeout: int = 30) -> RunResult:
        """Execute command on remote node via SSH."""
        ...
    
    def transfer_file(self, node_id: str, local: Path, remote: Path) -> None:
        """SCP file to remote node."""
        ...
```

**Tests**: `tests/test_target_manager.py` (mocked SSH)

---

### Task 2.2: Deploy Executor
**File**: `src/rw_blueprint/deployer/executor.py`  
**Effort**: 4h  
**Description**: Execute deployment plan: transfer files, reload systemd, start services.

```python
class DeployExecutor:
    def execute(self, plan: DeploymentPlan, target: str) -> DeploymentResult:
        """Execute deployment plan on target node."""
        for action in plan.actions:
            self._execute_action(action)
        return DeploymentResult(...)
    
    def _start_service(self, node: str, service: str) -> bool:
        """Start service with dependency ordering."""
        ...
```

**Tests**: `tests/test_deploy_executor.py`

---

### Task 2.3: Health Verifier
**File**: `src/rw_blueprint/deployer/verify.py`  
**Effort**: 2h  
**Description**: Verify service health after deployment.

```python
class HealthVerifier:
    def verify(self, node: str, service: str, timeout: int = 30) -> HealthStatus:
        """Check if service is healthy."""
        # Check systemctl status
        # Poll health endpoint if configured
        ...
```

**Tests**: `tests/test_health_verifier.py`

---

## Phase 3: Rollback & Recovery (0.5 day)

### Task 3.1: Deployment State Tracker
**File**: `src/rw_blueprint/deployer/state.py`  
**Effort**: 2h  
**Description**: Track deployment history per service per node.

```python
class DeploymentState:
    def record(self, node: str, service: str, deployment: DeploymentRecord) -> None:
        ...
    
    def get_previous_healthy(self, node: str, service: str) -> DeploymentRecord | None:
        ...
```

**Storage**: JSON file at `/var/lib/rw-blueprint/state/{node}/{service}.json`

---

### Task 3.2: Rollback Executor
**File**: `src/rw_blueprint/deployer/rollback.py`  
**Effort**: 2h  
**Description**: Implement rollback logic.

```python
class RollbackExecutor:
    def rollback(self, node: str, service: str) -> RollbackResult:
        """Rollback to previous healthy version."""
        ...
```

**Tests**: `tests/test_rollback.py`

---

## Phase 4: CLI Integration (0.5 day)

### Task 4.1: New CLI Commands
**File**: `src/rw_blueprint/cli.py`  
**Effort**: 3h  
**Description**: Add `plan`, `apply`, `rollback`, `status` commands.

```bash
rw-blueprint plan topology.yaml --nodes infra
rw-blueprint apply topology.yaml --nodes infra --dry-run=false
rw-blueprint rollback --node infra --service caddy
rw-blueprint status --node infra
```

---

### Task 4.2: Error Handling & Retry
**File**: `src/rw_blueprint/deployer/executor.py`  
**Effort**: 2h  
**Description**: Add retry logic with exponential backoff.

```python
def execute_with_retry(self, action, max_retries=3):
    for attempt in range(max_retries):
        try:
            return self.execute(action)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(5 * (2 ** attempt))
```

---

## Phase 5: Testing & Documentation (0.5 day)

### Task 5.1: Integration Tests
**Files**: `tests/integration/test_deploy_infra.py`  
**Effort**: 3h  
**Description**: End-to-end test deploying to infra node.

---

### Task 5.2: Documentation
**Files**: 
- `docs/DEPLOYMENT.md` — User guide
- `docs/ADR-021-deployment-engine-architecture.md` — ADR for deployment decisions

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/rw_blueprint/deployer/__init__.py` | CREATE | Package init |
| `src/rw_blueprint/deployer/graph.py` | CREATE | Dependency graph |
| `src/rw_blueprint/deployer/plan.py` | CREATE | Deployment plan |
| `src/rw_blueprint/deployer/targets.py` | CREATE | SSH target manager |
| `src/rw_blueprint/deployer/executor.py` | CREATE | Deploy executor |
| `src/rw_blueprint/deployer/verify.py` | CREATE | Health verifier |
| `src/rw_blueprint/deployer/state.py` | CREATE | Deployment state |
| `src/rw_blueprint/deployer/rollback.py` | CREATE | Rollback executor |
| `src/rw_blueprint/schema.py` | MODIFY | Add ServiceType |
| `src/rw_blueprint/cli.py` | MODIFY | Add deploy commands |
| `tests/test_dependency_graph.py` | CREATE | Graph tests |
| `tests/test_deployment_plan.py` | CREATE | Plan tests |
| `tests/test_deploy_executor.py` | CREATE | Executor tests |
| `tests/test_rollback.py` | CREATE | Rollback tests |
| `tests/integration/test_deploy_infra.py` | CREATE | Integration tests |

**Total**: 10 new files, 2 modified

---

## Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| SSH authentication failures | 🔴 High | Implement retry with credential fallback |
| Partial deployment on failure | 🟠 Medium | Transactional deploy (all-or-nothing) |
| Service dependency cycles | 🟠 Medium | Cycle detection before deployment |
| Health check timeouts | 🟡 Low | Configurable timeouts per service |
| Data loss on rollback | 🔴 High | Preserve volumes, test rollback procedure |

---

## Open Questions

1. **Secrets management**: Should we integrate with Vault/SOPS or use simple environment files for Phase 1?
2. **Configuration drift**: Should the controller also handle config file changes?
3. **Multi-node**: When do we tackle cross-node deployments?

---

## Sign-Off Required

- [ ] Specification approved
- [ ] Implementation plan approved
- [ ] Risk assessment accepted
- [ ] Timeline agreed

**Next Step**: User sign-off on this plan before TDD implementation begins.
