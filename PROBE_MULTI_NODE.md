# Probe Multi-Node Architecture Implementation

**Date**: 2026-09-14
**Status**: Working (srv1 node operational, remote containers blocked)

## Summary

Fixed probe architecture to support multi-node infrastructure observation with SSH fallback.

### Changes Made

| File | Change |
|------|--------|
| `probes/base.py` | Probe base class with `timeout`, `host_node` params |
| `probes/ssh.py` | New SSH helper module |
| `probes/multi_node.py` | New MultiNodeProbeCoordinator |
| `probes/{dns,incus,podman,port,tailscale}.py` | All 5 probes support local+SSH fallback |
| `cli.py` | New `--nodes` CLI flag for target selection |

### CLI Usage

```bash
# Probe single node (default)
rw-blueprint probe --nodes srv1 --output docs/live.json

# Probe multiple nodes (comma-separated)
rw-blueprint probe --nodes srv1,infra,enterprise,dev --output docs/live.json

# Run reconciliation
rw-blueprint reconcile topology.yaml docs/live.json --format summary
```

### Current Limitations

- **SSH to containers fails**: `sysop@100.79.58.118` (infra) returns "Permission denied"
- Workaround: Run from `srv1` host (where SSH key works) instead of workstation
- Podman on infra returns empty (`[]`) — containers may use different naming

### Probe Results (srv1 only)

| Probe | Nodes | Services | Links | Errors |
|-------|-------|----------|-------|--------|
| incus | 3 | 0 | 0 | 0 |
| port | 12 | 0 | 11 | 0 |
| tailscale | 5 | 0 | 4 | 0 |
| dns | 3 | 0 | 1 | 1 (rapidwebs.org timeout) |

### Drift Report (srv1-only)

- Total: 77 items
- Critical: 22 (services not observed on local host)
- Warning: 22
- Info: 33

### Next Steps (if needed)

1. Fix SSH to containers (generate/use SSH key for sysop user on infra)
2. Update topology.yaml to mark `cloudflare` as external (already done in ignore rules)
3. Generate drift report with ignore rules for known-acceptable deviations

## Files Modified (git)

- `src/rw_blueprint/cli.py`
- `src/rw_blueprint/probes/dns.py`
- `src/rw_blueprint/probes/incus.py`
- `src/rw_blueprint/probes/podman.py`
- `src/rw_blueprint/probes/port.py`
- `src/rw_blueprint/probes/tailscale.py`

## New Files

- `src/rw_blueprint/probes/ssh.py`
- `src/rw_blueprint/probes/multi_node.py`
- `docs/live-srv1.json`
- `docs/drift-report.json`

## Tests

All 80 tests passing: `uv run pytest tests/ -q`
