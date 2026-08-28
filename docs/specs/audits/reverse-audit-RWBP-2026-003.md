# Reverse Audit — RWBP-2026-003 (MCP + JSON/Exit-Codes + Remediation)

**SPEC Version**: 0.1.0 (Draft)
**Audit Date**: 2026-08-28
**Auditor**: Network Systems Specialist
**Mode**: MEDIUM (per plan-and-audit)

---

## Executive Summary

This reverse audit finds what SPEC RWBP-2026-003 **misses** — gaps, edge cases, and
security concerns not covered by the forward audit. Findings are prioritized by severity
with the specific location in the SPEC/ADR where the gap lives.

**Overall**: 3 high, 3 medium, 4 low findings. None are blocking, but G-1, G-3, and G-4
must be resolved in synthesis before the SPEC reaches v0.2.0.

---

## Findings

### 🔴 G-1 — "Drift report" MCP resource is semantically ambiguous (REQ-001)

- **Problem**: REQ-001 lists "the drift report" as an MCP *resource*, but a resource implies
  a stable, addressable (URI) data source. The drift report is **transient** — computed
  fresh on each `reconcile` invocation and never persisted.
- **Impact**: If implemented naively, the "resource" would be empty/stale or require
  persistence that violates the statelessness constraints (§5.2).
- **Resolution**: Define the *resource* as the `report` JSON **schema** (a stable, static
  artifact documenting the shape), while the *report itself* is a tool **return value**
  from `reconcile`. Do not persist reports.

### 🔴 G-3 — Exit-code contract conflicts with existing `--fail-on` (REQ-005)

- **Problem**: The existing `reconcile` CLI has `--fail-on {critical,warning,info,none}`
  (`cli.py:146-147`) which sets exit `1` on a severity threshold. The new contract
  (0/1/2) must specify how `--fail-on` interacts — otherwise there are two competing
  definitions of "drift exit."
- **Impact**: Ambiguous CI behavior; two flags fighting over exit codes.
- **Resolution**: Keep `--fail-on` as the *threshold* (which severities count as "drift" for
  exit purposes), but map the *outcome* to the new contract: `0` = no findings at/above
  threshold, `1` = findings present, `2` = error. Document this mapping explicitly.

### 🔴 G-4 — Remediation *direction* for `mismatched` is undefined (REQ-006)

- **Problem**: For a `mismatched` field (both exist, differ), the proposal could fix
  *declared→observed* or *observed→declared*. ADR-015 says "or vice-versa, depending on
  drift class" but never resolves which direction is correct for `mismatched`. The source of
  truth is **declared**, but a live correction (e.g. an operator fixed a port by hand) might
  legitimately mean declared is *wrong*.
- **Impact**: A wrong direction produces a proposal that, if approved, *reintroduces* drift
  or erases a legitimate human correction.
- **Resolution**: Default direction = **observed is authoritative for `mismatched`** (i.e.
  propose updating the *declared* model to match reality, since reality is what is running),
  BUT always render the direction explicitly in the proposal so a human can invert it. This
  matches Kausality's "declared vs intended" insight — the drift may reflect intent.

### 🟠 G-5 — Blast-radius source of truth (REQ-006)

- **Problem**: REQ-006 says blast-radius is "derived from the dependency graph," but the
  **live-state schema has no dependencies** (they are non-observable by design — ADR-0007).
- **Impact**: The blast-radius heuristic cannot consult live-state; it must consult the
  *declared* topology's `dependencies` list.
- **Resolution**: Specify blast-radius is computed from `topology.dependencies` (declared),
  not from live-state. For an `extra` entity (undeclared), blast-radius is unknown/`null`.

### 🟠 G-6 — `generate` and `probe` are not strictly read-only (REQ-003)

- **Problem**: REQ-003 asserts "no tool mutates the *declared model*" (correct), but
  `generate` **writes files** (artifacts to disk) and `probe` **reaches out over SSH**. These
  are side-effecting, though not model-mutating.
- **Impact**: MCP's approval-on-invocation should flag these; a blanket "read-only" framing
  undersells the risk of `generate` clobbering a directory.
- **Resolution**: Classify verbs: `validate`/`reconcile` = pure read-only; `generate` =
  write-artifacts (needs approval + explicit output dir); `probe` = read-only-but-network.
  Encode this in the MCP tool descriptions/annotations.

### 🟠 G-2 — `validate` JSON scope conflates two shapes (REQ-004/005)

- **Problem**: REQ-004 says "reconcile (and validate)" emit JSON, but `validate` has no
  drift — its JSON would be a *validation result*, not a *drift report*. Two different JSON
  shapes under one `--format json` flag.
- **Impact**: A consumer reading `--format json` output can't tell which shape it's getting.
- **Resolution**: Restrict the versioned drift-report JSON to `reconcile`. Give `validate` a
  distinct, simpler result shape (or leave it text-only for v0.1). Note in §9.

### 🔵 G-7 — MCP resource URI scheme unspecified (REQ-001)

- **Problem**: No URI scheme is defined for the `topology.yaml` and report-schema resources.
- **Resolution**: Adopt a simple `rw-blueprint://<name>` scheme (e.g.
  `rw-blueprint://schema/topology`, `rw-blueprint://schema/report`).

### 🔵 G-8 — Remediation array ordering not covered by determinism (REQ-008)

- **Problem**: REQ-008 asserts byte-stability of the report, but not that the `remediation`
  array is deterministically ordered (the `items` list ordering is sorted in the reconciler,
  but a parallel `remediation` array must be too).
- **Resolution**: Specifify remediation entries are ordered by `(entity_type, entity_id,
  field)`, matching the sorted finding order.

### 🔵 G-9 — MCP tool input schemas could leak host topology (REQ-003 / §5.3)

- **Problem**: `probe`'s tool signature may expose target hostnames/IPs in its description or
  defaults, which is minor information disclosure in a shared MCP context.
- **Resolution**: Keep tool descriptions generic ("target host" not "srv1.rapidwebs.org");
  no host-specific defaults in signatures.

### 🔵 G-10 — FastMCP API stability across the `1.x` pin (REQ-001)

- **Problem**: ADR-013 pins `mcp>=1.27,<2`, but FastMCP's decorator surface has shifted
  across 1.x minors.
- **Resolution**: Add a smoke test that registers the server and asserts 4 tools/2 resources
  exist, so a dependency bump that breaks registration fails loudly.

---

## Reverse Audit Verdict

**SPEC RWBP-2026-003 v0.1.0 has no blocking gaps.** G-1, G-3, G-4 (high) and G-5, G-6, G-2
(medium) must be resolved in the v0.2.0 synthesis. G-7 through G-10 (low) are additive
clarifications.

---

## Reverse Audit Checklist
- [x] Dead code / stale references checked (N/A — no implementation yet)
- [x] Contract drift between SPEC and existing code identified (REQ-004/005 vs cli.py)
- [x] Security surface analyzed (MCP read-only, secret leakage, side-effects)
- [x] Determinism edge cases (remediation ordering, timestamp exclusion)
- [x] Ambiguous semantics flagged (resource vs return, remediation direction, validate scope)
- [x] Cross-document consistency (ADR-0007 no-deps vs REQ-006 blast-radius)
- [x] Severity-classified findings with resolution guidance
