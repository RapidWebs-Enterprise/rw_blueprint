# ADR-019: Controller Pattern for Service Lifecycle Management

**Status**: Accepted  
**Date**: 2026-09-15  
**Context**: rw_blueprint needs to not just describe infrastructure, but actively maintain it

## 1. Decision

Adopt the **Controller Pattern** (from Kubernetes) for managing service lifecycle. A controller continuously reconciles desired state (topology.yaml) with actual state (live probes), automatically correcting drift.

## 2. Motivations

- Declarative YAML is source of truth
- Manual interventions cause drift
- Services crash, need auto-restart
- Configuration changes need auto-propagation
- Human operators should not manage individual services

## 3. Consequences

### Positive
- Infrastructure self-heals
- Drift is automatically corrected
- Consistent state across restarts
- Audit trail via reconciliation logs

### Negative
- Controller runs continuously (resource cost)
- Complexity in failure modes
- Need to handle concurrent modifications
- Learning curve for operators

## 4. Implementation

```python
class ServiceController:
    def __init__(self, topology, node_manager):
        self.topology = topology
        self.node_manager = node_manager
    
    def reconcile(self, node_id: str):
        """Main control loop iteration."""
        desired = self.topology.get_services_for_node(node_id)
        actual = self.probe_services(node_id)
        
        drift = self.compare(desired, actual)
        
        for change in drift.approved_changes:
            self.apply(change)
            self.verify(change)
        
        return drift.report()
    
    def run_loop(self, node_id: str, interval: timedelta):
        """Continuous reconciliation."""
        while True:
            try:
                self.reconcile(node_id)
            except Exception as e:
                self.log_error(e)
            time.sleep(interval)
```

## 5. Alternatives Considered

### 5.1 Push-Based (CI/CD)
- Run deployment on schedule or trigger
- **Rejected**: Doesn't handle drift, requires external trigger

### 5.2 Event-Driven (File Watcher)
- Watch topology.yaml for changes
- **Rejected**: Doesn't handle runtime drift, crashes

### 5.3 Manual with Reports
- Generate reports, operator acts
- **Rejected**: Too slow, error-prone

## 6. References

- [Kubernetes Controllers](https://kubernetes.io/docs/concepts/architecture/controller/)
- [GitOps Continuous Reconciliation](https://www.gitops.tech/)
