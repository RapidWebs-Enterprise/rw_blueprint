# Synthesis — RWBP-2026-002 (Reconcile/Probe/Watchdog Layer)

**SPEC Version**: 0.1.0 → 0.2.0  
**Synthesis Date**: 2026-08-27  
**Synthesizer**: Network Systems Specialist  
**Mode**: MEDIUM (per plan-and-audit)

---

## Executive Summary

This synthesis combines the forward audit (validation of what's written) and reverse audit (gaps in what's written) into a revised SPEC v0.2.0 and updated ADRs. All 8 gaps from the reverse audit are resolved with concrete decisions. Three open questions from SPEC §9 are answered.

---

## Resolved Decisions

### D-01: Live-state projection mechanism → **Thin subclasses (Option B)**

**Decision**: Live-state `Node`/`Service`/`Link` are thin Pydantic subclasses of the topology schema's models, with non-observable fields made optional. A factory function converts declared → live-state shape.

**Rationale**: 
- Reuses validation logic from topology schema
- Honestly represents that live-state may lack `zone`, `host`, `image`, etc.
- Round-trip losslessness is preserved (declared → live-state → declared works)
- Probes emit into the live-state shape directly

**Implementation**: New module `rw_blueprint.live_state` with:
- `LiveNode`, `LiveService`, `LiveLink` (subclasses with optional non-observable fields)
- `LiveState` root model (nodes, services, links only)
- `to_live_state(topology: Topology) -> LiveState` factory

---

### D-02: Probe transport → **Central-over-SSH (gateway-tier)**

**Decision**: Probes run centrally on the machine invoking `rw-blueprint reconcile`, reaching targets via SSH/Tailscale using the existing SSH config (keys in `~/.ssh`, `ssh` command).

**Rationale**:
- RWDN is small: 1 host + 3 containers, all reachable via Tailscale
- No agent deployment needed on targets
- Simpler credential model (existing SSH keys)
- Matches the "gateway tier" pattern from OpenTelemetry research

**Implementation**: 
- Probe functions take a `target: str` (host alias: `srv1`, `infra`, `enterprise`, `dev`)
- Execution via `ssh {target} {command}` with configurable timeout
- SSH config handles keys, hostnames, Tailscale routing

---

### D-03: Drift report schema → **Defined as Pydantic model with versioning**

**Decision**: Drift report is a structured Pydantic model with its own `schema_version` (starting at `0.1`), emitted as JSON (primary) or YAML.

**Schema**:
```python
class DriftFinding(BaseModel):
    category: Literal["missing", "extra", "mismatched"]
    severity: Literal["critical", "high", "medium", "low"]
    entity_kind: Literal["node", "service", "link"]
    entity_id: str
    field: str | None = None  # None for missing/extra (whole entity)
    declared_value: Any | None = None
    observed_value: Any | None = None
    message: str


class DriftReport(BaseModel):
    schema_version: str = "0.1"
    topology_version: str  # from topology.yaml metadata.updated or hash
    live_state_version: str  # from live_state metadata or hash
    timestamp: datetime  # ISO 8601, UTC
    findings: list[DriftFinding]
    probe_errors: list[ProbeError]  # separate from findings
```

---

### D-04: Probe error handling → **Separate top-level key, partial failure continues**

**Decision**: Probe errors are collected in `probe_errors[]` (separate from `findings[]`). Partial probe failure continues other probes. Timeout = 30s default, configurable. Auth failure = recorded as error, probe marked unavailable.

**ProbeError schema**:
```python
class ProbeError(BaseModel):
    probe: str
    target: str
    error_type: Literal["timeout", "auth_failed", "command_not_found", "unexpected"]
    message: str
```

---

### D-05: Watchdog event change-type taxonomy → **Four types for v0.1**

**Decision**: Minimal taxonomy: `created`, `updated`, `deleted`, `restarted`.

**Event schema**:
```python
class WatchdogEvent(BaseModel):
    schema_version: str = "0.1"
    entity_kind: Literal["node", "service", "link"]
    entity_id: str
    change_type: Literal["created", "updated", "deleted", "restarted"]
    timestamp: datetime
    payload: dict  # live-state fragment delta
```

---

### D-06: Probe scheduling → **External (cron/systemd timer) for v0.1**

**Decision**: The `reconcile` command is stateless and idempotent, designed for external scheduling. Recommended: `*/5 * * * *` with `sleep $((RANDOM % 30))` splay. Internal scheduler deferred.

---

### D-07: Drift report schema versioning → **Added (see D-03)**

**Decision**: Drift report has its own `schema_version` field, independent of topology/live-state versions.

---

### D-08: Credential reference mechanism → **SSH config for v0.1**

**Decision**: Probes use existing SSH config (`~/.ssh/config`, keys, `ssh` command). No additional credential store for v0.1. Documented as assumption.

---

### D-09: Severity model → **4-level (critical/high/medium/low) for v0.1**

**Decision**: 4-level is sufficient. Agent's bounded-autonomy budget maps: `critical` → immediate HITL, `high` → next heartbeat, `medium` → next cycle, `low` → log only.

---

### D-10: Ignore-rule scope → **Exact-match (entity_id + field) for v0.1**

**Decision**: Exact-match only. Wildcards deferred.

---

## Updated SPEC v0.2.0 — Key Changes

| Section | Change |
|---------|--------|
| §2.3 Assumptions | Added: "Probes run centrally over SSH using existing SSH config" |
| §4.1 REQ-001 | Added: "Live-state uses thin subclasses of topology models with non-observable fields optional" |
| §4.2 REQ-002 | Added: "Probes execute via SSH to target hosts; timeout 30s default" |
| §4.3 REQ-003 | Added: "Drift report conforms to `DriftReport` schema (JSON/YAML) with `schema_version`" |
| §4.4 REQ-004 | Added: "Severity is 4-level; mapping to agent budget documented" |
| §4.5 REQ-005 | Added: "Ignore rules are exact-match (entity_id + field)" |
| §4.6 REQ-006 | Added: "Watchdog event change_type ∈ {created, updated, deleted, restarted}" |
| §4.7 REQ-007 | Unchanged (already strong) |
| §4.8 REQ-008 | Added: "Probe output ordering is alphabetical by probe name" |
| §4.9 REQ-009 | Added: "Drift report schema_version enforced" |
| §5.2 Reliability | Added: "Probe errors collected in `probe_errors[]`, separate from findings" |
| §7 Architecture | Added: "Live-state module uses thin subclasses; probe transport is SSH" |
| §9 Resolved Decisions | All 10 decisions documented |
| §10.2 Change Log | v0.2.0 entry added |

---

## ADR Updates

| ADR | Change |
|-----|--------|
| 0007 | Status → **Accepted**; Implementation Approach updated to "thin subclasses" |
| 0008 | Status → **Accepted**; Severity model documented as 4-level |
| 0009 | Status → **Accepted**; Probe transport documented as central-over-SSH |
| 0010 | Status → **Accepted**; No change |
| 0011 | Status → **Accepted**; No change |
| 0012 | Status → **Accepted**; No change |

---

## Implementation Plan Preview

The resolved decisions map to these implementation phases:

| Phase | Deliverable | Key Files |
|-------|-------------|-----------|
| **A1** | Live-state projection module | `src/rw_blueprint/live_state.py` |
| **A2** | Probe registry + 5 probes (incus, podman, port, dns, tailscale) | `src/rw_blueprint/probes/` |
| **A3** | Reconciler (diff engine) + drift report schema | `src/rw_blueprint/reconciler.py` |
| **A4** | CLI `reconcile` command wiring | `src/rw_blueprint/cli.py` |
| **A5** | Watchdog event schema (contract only) | `src/rw_blueprint/watchdog.py` |
| **A6** | Tests (unit + integration) | `tests/test_live_state.py`, `tests/test_probes.py`, `tests/test_reconciler.py` |
| **A7** | Example live-state docs | `examples/live_state.yaml`, `examples/live_state_drifted.yaml` |

**Estimated effort**: ~40h (MEDIUM mode: 5+ files, new capability, reusable feature)

---

## Sign-off Required

Before TDD implementation begins, the following must be approved:

1. **SPEC v0.2.0** — `docs/specs/RWBP-2026-002.SPEC.md` (to be updated)
2. **ADRs 0007–0012** — Status → Accepted, decisions recorded
3. **Implementation Plan** — `docs/plans/RWBP-2026-002-v0.2.0.md` (to be created)

---

## Next Steps

1. Update SPEC to v0.2.0 with resolved decisions
2. Update ADRs 0007–0012 to Accepted status
3. Write implementation plan
4. **User sign-off** on all three
5. TDD implementation (Phase A1–A7)
6. Adversarial audit, bug review, lint, test/perf/sec docs
7. Final forward audit → all PASS