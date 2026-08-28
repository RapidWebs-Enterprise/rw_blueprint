# Synthesis — RWBP-2026-003 (MCP + JSON/Exit-Codes + Remediation)

**From**: Forward + Reverse audits of SPEC RWBP-2026-003 v0.1.0
**Date**: 2026-08-28
**Auditor**: Network Systems Specialist
**Mode**: MEDIUM (per plan-and-audit)

---

## Purpose

This synthesis resolves the open issues (§9) and the reverse-audit findings (G-1…G-10)
into ratified decisions that flow into SPEC v0.2.0 and the implementation plan.

---

## Resolved Decisions

### D-01 — Remediation format → **JSON Patch (RFC 6902)**
JSON Patch is deterministic, diff-friendly, machine-consumable, and matches the "minimal
diff" reference (gitops-drift-remediation-agent). Each `remediation` entry carries a
`patch: list[dict]` in RFC 6902 form (`op`, `path`, `value`). (Resolves §9 + G-4's
representation.)

### D-02 — Blast-radius source → **declared topology `dependencies`**
Live-state has no dependencies (ADR-0007). Blast-radius is computed from
`topology.dependencies` (declared), depth/count heuristic. For an `extra` (undeclared)
entity, blast-radius is `null` (unknown). (Resolves G-5.)

### D-03 — `validate` JSON scope → **restrict the versioned drift-report JSON to `reconcile`**
`validate` keeps its existing pass/fail text output (no drift report, no JSON for v0.1).
The exit-code contract (0/1/2) and `--format json` apply to `reconcile` only. (Resolves
§9 + G-2.)

### D-04 — MCP "drift report" resource → **the report JSON *schema*, not a persisted report**
The report is transient (computed per reconcile). The stable MCP *resource* is the report
JSON schema document; the report itself is the `reconcile` tool's **return value**. No
report persistence (preserves §5.2 statelessness). (Resolves G-1.)

### D-05 — Exit codes + `--fail-on` → **threshold + outcome mapping**
`--fail-on` remains the *severity threshold* (which findings count as "drift"). Outcome is
mapped to the new contract: `0` = no findings at/above threshold, `1` = findings present,
`2` = error (invalid input, parse failure). Error paths move from `Exit(1)` → `Exit(2)`.
(Resolves G-3 + forward-audit REQ-005.)

### D-06 — Remediation direction for `mismatched` → **observed is authoritative; direction is explicit**
For `mismatched`, the proposal updates the *declared* model to match observed reality (what
is actually running), because reality is what's live. The direction (`declared → observed`)
is always rendered explicitly in the proposal so a human can invert it (Kausality's
"declared vs intended" insight). (Resolves G-4.)

### D-07 — Verb classification (MCP annotations) → **three classes**
`validate`/`reconcile` = pure read-only; `generate` = write-artifacts (needs approval +
explicit output dir); `probe` = read-only-but-network. Encoded in tool descriptions and the
MCP `annotations` field. (Resolves G-6.)

### D-08 — MCP resource URI scheme → **`rw-blueprint://<kind>/<name>`**
`rw-blueprint://schema/topology` and `rw-blueprint://schema/report`. (Resolves G-7.)

### D-09 — Remediation ordering → **`(entity_type, entity_id, field)`**
Deterministic, matching the reconciler's sorted finding order. (Resolves G-8.)

### D-10 — Tool description hygiene → **generic descriptions, no host-specific defaults**
Tool signatures describe behavior ("target host"), never hardcode `srv1.rapidwebs.org` or
IPs. (Resolves G-9.)

### D-11 — FastMCP registration smoke test → **mandatory**
A test registers the server and asserts exactly 4 tools + 2 resources, so a `mcp` 1.x bump
that breaks the decorator surface fails loudly. (Resolves G-10.)

---

## Outcome

- **SPEC** RWBP-2026-003 → **v0.2.0** (adds a "Resolved Decisions" section; §9 closed).
- **ADRs**: 0013 (MCP), 0015 (remediation), 0017 (machine-readable) → **Accepted**.
  ADR-0018 (config/naming) remains **Proposed (deferred)**.
- **Implementation plan** → `IMPL-RWBP-2026-003.md` (next step).

No implementation proceeds until user sign-off on SPEC v0.2.0 + ADRs 0013/0015/0017.
