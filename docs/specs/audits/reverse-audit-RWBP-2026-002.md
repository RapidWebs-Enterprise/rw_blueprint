# Reverse Audit — RWBP-2026-002 (Reconcile/Probe/Watchdog Layer)

**SPEC Version**: 0.1.0 (Draft)  
**Audit Date**: 2026-08-27  
**Auditor**: Network Systems Specialist  
**Mode**: MEDIUM (per plan-and-audit)

---

## Executive Summary

This reverse audit systematically finds what the SPEC (RWBP-2026-002) and its ADRs **miss** — gaps, edge cases, unstated assumptions, and implementation risks that aren't covered by the forward audit's validation of what *is* written.

**Overall**: The SPEC is solid but has **8 gaps** ranging from critical to low. Most are omissions that will surface during implementation if not addressed now.

---

## Gap Classification

| ID | Severity | Category | Summary |
|----|----------|----------|---------|
| G-01 | 🔴 Critical | Schema | Live-state projection mechanism unspecified (same classes vs subclasses) |
| G-02 | 🔴 Critical | Probe | Probe transport (local vs SSH) unresolved — affects entire probe architecture |
| G-03 | 🟠 High | Reconciler | Drift report output format/schema not specified |
| G-04 | 🟠 High | Probe | Probe error handling contract unspecified (partial failure, timeout, auth) |
| G-05 | 🟠 High | Watchdog | Watchdog event change-type taxonomy undefined |
| G-06 | 🟡 Medium | Probe | Probe scheduling/splay mechanism not specified |
| G-07 | 🟡 Medium | Reconciler | Drift report schema versioning not addressed |
| G-08 | 🔵 Low | Security | Credential reference mechanism for probes not specified |

---

## Detailed Findings

### G-01: Live-state projection mechanism unspecified 🔴 Critical

**What's missing**: The SPEC says live-state is a "projection" of the topology schema (REQ-001, ADR-007), but doesn't specify *how*:
- Option A: Reuse the exact same Pydantic classes (`Node`, `Service`, `Link`) from `schema.py`
- Option B: Thin subclasses with non-observable fields omitted
- Option C: Separate Pydantic models that happen to share field names

**Why it matters**: This is the central architectural decision for the live-state module. It affects:
- Code reuse vs duplication
- Validation behavior (e.g., `Node` requires `zone` and `host` — but live-state may not have them)
- Round-trip losslessness (REQ-008, NFR 5.2)
- The "shared vocabulary" promise

**Evidence from research**: The "Live_State_Schema_Projection_Contract" report says "probes must map their raw output into the projection shape" — implying the projection shape is a *target* that probes emit into, not necessarily the same as the declared model.

**Recommendation**: Resolve in implementation plan. My lean: **Option B (thin subclasses)** — live-state `Node`/`Service`/`Link` are subclasses that make non-observable fields optional, with a factory to convert from declared → live-state shape.

---

### G-02: Probe transport unresolved 🔴 Critical

**What's missing**: The SPEC lists 5 probes but doesn't specify *how* they reach their targets:
- **Local/agent-tier**: Probe runs on the target host (requires agent on each host)
- **Central/gateway-tier**: Probe runs centrally, reaches targets over SSH/Tailscale

**Why it matters**: This affects the entire probe architecture:
- Code structure (local vs remote execution)
- Credential handling (G-08)
- Failure modes (network partition vs local failure)
- Deployment model (what runs where)

**Evidence from research**: The "Probe_Collector_Plugin_Architecture" report notes "the research leans agent-tier (local, lightweight), but the RWDN's small size may make central-over-SSH simpler." The SPEC §9 correctly flags this as open.

**RWDN context**: 1 Hetzner host (`srv1`) + 3 Incus containers (`infra`, `enterprise`, `dev`). All reachable via Tailscale. Central-over-SSH is genuinely simpler here — no agent deployment needed.

**Recommendation**: Decide in implementation plan. For RWDN size, **central-over-SSH** is the pragmatic choice. Document this explicitly.

---

### G-03: Drift report output format/schema not specified 🟠 High

**What's missing**: REQ-003 says "a drift report is emitted" but doesn't specify:
- Output format: JSON? YAML? Both?
- Field names and structure of a finding
- Whether the report includes metadata (timestamp, topology version, live-state version)
- Whether findings are grouped by entity or flat list

**Why it matters**: The drift report is the **primary output contract** consumed by the agent (P5). Without a defined schema:
- Agent cannot reliably parse findings
- Tests cannot assert exact output
- Forward compatibility is impossible

**Evidence from research**: Both tfdrift and driftguard have structured drift report schemas (JSON with finding arrays, severity, metadata). The "Declared_vs_Actual" report emphasizes the drift report is the "stable output contract consumed by the agent."

**Recommendation**: Define the drift report schema in the implementation plan as a Pydantic model. Include: `findings[]` (each with `category`, `severity`, `entity_id`, `entity_kind`, `field`, `declared_value`, `observed_value`, `message`), `metadata` (timestamp, topology_version, live_state_version, probe_errors[]).

---

### G-04: Probe error handling contract unspecified 🟠 High

**What's missing**: NFR 5.2 says "A probe that fails to reach its target SHALL emit a descriptive error (or a `probe_error` finding), never a crash or silent empty result." But the SPEC doesn't specify:
- What constitutes a "probe error" vs a "drift finding"
- Whether partial probe failure aborts the whole reconcile or continues
- Timeout behavior
- Authentication failure handling
- Whether probe errors appear in the drift report or are separate

**Why it matters**: Probes *will* fail (host down, SSH auth changed, command not found). The reconciler must handle this gracefully and the drift report must distinguish "I couldn't check" from "I checked and it's wrong."

**Evidence from research**: The "Probe_Collector_Plugin_Architecture" report emphasizes probes are read-only but can fail. osquery handles this with "query packs" that can partially fail.

**Recommendation**: Define in implementation plan:
- Probe errors are separate from drift findings (different top-level key in report)
- Partial failure = continue other probes, collect errors
- Timeout = configurable (default 30s), error recorded
- Auth failure = error recorded, probe marked unavailable

---

### G-05: Watchdog event change-type taxonomy undefined 🟠 High

**What's missing**: REQ-006 says the event has a "change type" but doesn't define the taxonomy.

**Why it matters**: The watchdog contract is defined now (ADR-009) but the change types are the vocabulary that push emitters will use. Without a defined taxonomy:
- Different watchdogs will invent different change types
- The reconciler's event→live-state conversion will be ambiguous
- The "emit is untrusted" boundary (ADR-011) can't be validated

**Evidence from research**: Kubernetes watch events use `ADDED`/`MODIFIED`/`DELETED`/`ERROR`. osquery event publishers use `added`/`removed`/`modified`. The "Event_Driven_Watchdog_Push_Architecture" report says the event shape must be "convertible to a live-state fragment update."

**Recommendation**: Define in implementation plan. Minimal taxonomy for v0.1:
- `created` — new entity appeared (service started, container created)
- `updated` — existing entity changed (port changed, image updated)
- `deleted` — entity disappeared (service stopped, container destroyed)
- `restarted` — entity cycled (container restart — distinct from updated)

---

### G-06: Probe scheduling/splay mechanism not specified 🟡 Medium

**What's missing**: The SPEC mentions "heartbeat cadence" and "splay" (Definition §3) but doesn't specify:
- How probes are scheduled (cron? systemd timer? in-process scheduler?)
- Splay/jitter mechanism to avoid thundering herd
- Whether all probes run sequentially or in parallel
- Whether scheduling is part of this layer or external (cron)

**Why it matters**: The "pull-first" loop (ADR-009) needs a scheduling mechanism. If it's external (cron), that's a deployment detail. If it's internal, it's code.

**Evidence from research**: The "Declared_vs_Actual" report notes Kubernetes controllers use "level-triggered" reconciliation with jitter. The "Probe_Collector" report mentions "splay" as a defined term.

**Recommendation**: For v0.1, **external scheduling via cron/systemd timer** — the `reconcile` command is stateless and idempotent, designed to be invoked on a schedule. Document the recommended cron schedule (e.g., every 5 minutes with 30s splay). Internal scheduler can be added later if needed.

---

### G-07: Drift report schema versioning not addressed 🟡 Medium

**What's missing**: The topology schema has `schema_version` enforcement (RWBP-2026-001, `schema.py` line 156-163). The live-state projection will need the same (REQ-009). But the **drift report itself** has no versioning.

**Why it matters**: The agent (P5) will consume drift reports. If the drift report format changes, the agent breaks. Versioning the drift report schema from day one prevents this.

**Recommendation**: Add `schema_version` to the drift report model (separate from topology/live-state version). Start at `0.1`. Include in implementation plan.

---

### G-08: Credential reference mechanism for probes not specified 🔵 Low

**What's missing**: Probes need to reach targets (SSH to `srv1`, `infra`, `enterprise`, `dev`). The SPEC says "probes reference credentials by name only; values live in the credential store" (Scope §2.2) but doesn't specify:
- What "credential store" means (env vars? file? keyring? 1Password CLI?)
- How probes discover which credential to use for which host
- Whether credentials are per-host or per-probe

**Why it matters**: Without this, probes can't actually run. It's a deployment/runtime concern but affects the probe interface.

**RWDN context**: Current SSH access is `ssh srv1`, `ssh infra`, etc. — using SSH keys. Tailscale provides mesh connectivity. The simplest model: probes use the existing SSH config (keys in `~/.ssh`, `ssh` command), no additional credential store needed for v0.1.

**Recommendation**: For v0.1, **assume SSH key-based auth via existing `ssh` config**. Document this assumption. A proper credential store can be added later if needed.

---

## Additional Observations (Not Gaps, But Worth Noting)

### O-01: Example `topology.yaml` for testing
The SPEC doesn't require a canonical example topology for testing the reconcile layer. The core engine has `examples/topology.yaml` — the reconcile layer should have a corresponding `examples/live_state.yaml` (matching) and `examples/live_state_drifted.yaml` (with known drift) for integration tests.

### O-02: Probe output ordering
For determinism (REQ-008), probe output ordering must be stable. The registry should iterate probes in a defined order (e.g., alphabetical by name).

### O-03: Live-state document composition
The SPEC doesn't specify how multiple probe fragments are composed into a single `live_state` document. Is it a merge? A concatenation? The reconciler needs a single `live_state` input.

### O-04: External entity handling in live state
The topology schema models external entities (Cloudflare, internet) as `Node` with `type: external`. Probes won't observe these. The reconciler must handle "declared external node has no live-state counterpart" gracefully (not a `missing` finding).

---

## Reverse Audit Verdict

**The SPEC is buildable but has 8 gaps that must be resolved in the implementation plan before TDD begins.** The two critical gaps (G-01, G-02) are architectural decisions that will cascade through the entire implementation. The three high gaps (G-03, G-04, G-05) are output contracts that the agent and tests depend on.

**Recommendation**: Resolve all 8 gaps in the implementation plan (next step after synthesis), then proceed to sign-off and TDD.

---

## Reverse Audit Checklist

- [x] Dead code — N/A (no implementation yet)
- [x] Stale test files — N/A
- [x] .gitignore gaps — N/A
- [x] Duplicate functionality — Checked: no overlap with RWBP-2026-001
- [x] Broken imports — N/A
- [x] Secrets in repo — Checked: SPEC explicitly forbids secrets in live-state/drift/events
- [x] Oversized files — N/A
- [x] Inconsistent naming — Checked: consistent with RWBP-2026-001
- [x] Missing __init__.py — N/A
- [x] Uncommitted work — N/A
- [x] Path traversal risks — Checked: SPEC requires probes to be read-only, no file_path params
- [x] Test/code contract drift — N/A (no tests yet)
- [x] Missing test dependencies — N/A
- [x] Subprocess safety — Flagged in G-04 (probe execution)
- [x] Error key consistency — Flagged in G-03 (drift report schema)