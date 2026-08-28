# Forward Audit — RWBP-2026-002 (Reconcile/Probe/Watchdog Layer)

**SPEC Version**: 0.1.0 (Draft)  
**Audit Date**: 2026-08-27  
**Auditor**: Network Systems Specialist  
**Mode**: MEDIUM (per plan-and-audit)

---

## Executive Summary

This forward audit validates the SPEC (RWBP-2026-002) and its six ADRs (0007–0012) for internal consistency, actionability, and alignment with the research corpus. **No implementation exists yet** — this audit checks that the specification is a sound, buildable contract before any code is written.

**Overall**: ✅ **SPEC is internally consistent and actionable**. All 9 functional requirements are well-formed with testable acceptance criteria. The six ADRs form a coherent architectural foundation. Three open questions in §9 are correctly flagged for the audit phase.

---

## Requirement-by-Requirement Validation

### REQ-001: Live-state projection schema
**Status**: ✅ **Well-formed and actionable**

- **Schema projection concept** is clearly defined: live-state reuses `Node`/`Service`/`Link` shapes from topology schema, omits `Zone`/`Dependency` (non-observable).
- **Acceptance criteria** are measurable: parse test, id semantics match, non-observable entities absent.
- **Alignment with ADR-007**: Directly implements the projection decision.
- **Alignment with research**: Matches "Live_State_Schema_Projection_Contract" finding that projection makes diff mechanical and vocabulary shared.
- **Gap**: The SPEC doesn't specify whether `live_state` uses the *same* Pydantic classes or thin subclasses. This is an implementation detail but should be resolved in the implementation plan.

### REQ-002: Probe registry with read-only collectors
**Status**: ✅ **Well-formed and actionable**

- **Probe contract** is clear: each probe emits a normalized fragment, performs no mutation.
- **Acceptance criteria** are testable: fragment conforms to live-state schema; mutation test (negative assertion).
- **Alignment with ADR-010**: In-process registry, no plugin framework.
- **Alignment with ADR-012**: Borrows osquery model (declarative observation, uniform output).
- **Alignment with research**: Matches "Probe_Collector_Plugin_Architecture" finding that probes are read-only by construction.
- **Gap**: The SPEC lists 5 initial probes (`incus`, `podman`, `port`, `dns`, `tailscale`) but doesn't specify the *transport* (local vs SSH). This is correctly flagged as open question in §9.

### REQ-003: Reconcile command with three-way drift classification
**Status**: ✅ **Well-formed and actionable**

- **Three-way classification** (missing/extra/mismatched) is the universal contract per research.
- **Acceptance criteria** are precise and testable: each category has a concrete scenario.
- **Alignment with ADR-008**: Directly implements the three-way classification decision.
- **Alignment with research**: Matches "Declared_vs_Actual_Reconciliation_Control_Loop_Patterns" and reference projects (tfdrift, driftguard).
- **Gap**: The SPEC doesn't specify the *output format* of the drift report (JSON vs YAML, field names). This should be defined in the implementation plan.

### REQ-004: Severity assignment
**Status**: ⚠️ **Well-formed but severity model needs resolution**

- **Requirement** is clear: each finding gets a severity derived from entity role + drift nature.
- **Acceptance criteria** give concrete examples (missing min-stack = high, extra unplanned = medium, cosmetic mismatch = low).
- **Alignment with ADR-008**: Severity is a pure function of (entity kind, drift category, field).
- **Open question in §9**: "Is a 4-level model sufficient, or does the agent need a finer-grained signal (e.g. numeric score)?"
- **Recommendation**: The 4-level model is sufficient for v0.1. The agent's bounded-autonomy budget can map severity → action budget. Document this decision in the implementation plan.

### REQ-005: Ignore rules
**Status**: ✅ **Well-formed and actionable**

- **Ignore rule contract**: keyed by entity id + field, declared (not hardcoded), versioned.
- **Acceptance criteria** are testable: matching finding suppressed/marked ignored.
- **Alignment with research**: tfdrift and driftguard both support ignore rules.
- **Open question in §9**: "Should ignore rules support wildcard/pattern matching?"
- **Recommendation**: Start with exact-match (entity id + field) for v0.1. Wildcards add complexity and can be added later if needed.

### REQ-006: Watchdog event contract
**Status**: ✅ **Well-formed and actionable**

- **Event shape**: entity id, change type, timestamp, payload — convertible to live-state fragment.
- **Acceptance criteria** are testable: shape defined, convertible, no secrets.
- **Alignment with ADR-009**: Contract defined now, implementation deferred.
- **Alignment with research**: Matches "Event_Driven_Watchdog_Push_Architecture" finding that emit is untrusted, apply is gated.
- **Gap**: The SPEC doesn't specify the *change type* taxonomy (created/updated/deleted/restarted). Should be defined in implementation plan.

### REQ-007: Emit-is-untrusted / apply-is-gated boundary
**Status**: ✅ **Well-formed and actionable**

- **Hard boundary** is clearly stated: no component writes to declared model; reconciler only outputs drift report; applying is HITL-gated.
- **Acceptance criteria** are testable: code audit for write paths, reconciler output check.
- **Alignment with ADR-011**: Directly implements the security boundary decision.
- **Alignment with research**: Matches "Event_Driven_Watchdog_Push_Architecture" and the "agent is the reward, not a shortcut" principle.
- **Strength**: This is the most critical security property and it's correctly enforced by construction.

### REQ-008: Determinism
**Status**: ✅ **Well-formed and actionable**

- **Requirement**: identical declared + observed → identical drift report (byte-for-byte).
- **Acceptance criteria**: two runs produce identical output.
- **Alignment with architecture constraints**: "Stable field ordering; no timestamps in drift report body."
- **Testability**: Straightforward — run twice, diff output.

### REQ-009: Malformed live-state rejection
**Status**: ✅ **Well-formed and actionable**

- **Strict schema enforcement**: unknown fields, dangling references, unsupported schema_version all rejected.
- **Acceptance criteria** map directly to Pydantic v2 `extra="forbid"` + custom validators.
- **Alignment with topology schema**: The topology schema already enforces this pattern (see `schema.py` lines 51-54, 155-163, 165-200).
- **Consistency**: The live-state projection should reuse the same strictness pattern.

---

## ADR Coherence Check

| ADR | Decision | Consistent with SPEC? | Notes |
|-----|----------|----------------------|-------|
| 0007 | Live-state as projection | ✅ | Directly implements REQ-001 |
| 0008 | Three-way classification + severity | ✅ | Directly implements REQ-003, REQ-004 |
| 0009 | Pull-first sequencing | ✅ | Scope §2.3 correctly defers watchdog implementation |
| 0010 | In-process probe registry | ✅ | Directly implements REQ-002 |
| 0011 | Emit-untrusted / apply-gated | ✅ | Directly implements REQ-007 |
| 0012 | Osquery model, not tool | ✅ | Informs probe design (REQ-002) |

**All six ADRs are mutually consistent and collectively support the SPEC.**

---

## Cross-Reference Validation

### With RWBP-2026-001 (Core Engine)
- ✅ **Schema reuse**: SPEC §7 requires reusing Pydantic v2 topology schema — the live-state projection will reuse `Node`/`Service`/`Link` models from `schema.py`.
- ✅ **Stack consistency**: Python 3.11+, Pydantic v2, PyYAML, Typer, Rich — same as core engine.
- ✅ **Schema version enforcement**: Core engine enforces `schema_version` (line 156-163); SPEC REQ-009 requires same for live-state.

### With Research Corpus
All 10 research reports are cited in SPEC §10.1. Key alignments verified:
- Kubernetes reconcile loop → REQ-003, REQ-008
- Three-way classification (driftctl/tfdrift/driftguard) → REQ-003, ADR-008
- Pull-first (Kubernetes "watch is optimization") → ADR-009
- Probe read-only by construction → REQ-002, ADR-010
- Emit-untrusted/apply-gated → REQ-007, ADR-011
- Osquery model (declarative, uniform, on-demand) → ADR-012

### With Reference Projects
- **tfdrift**: Drift CLI with structured reports, severity, watch mode, ignore rules → validates REQ-003, REQ-004, REQ-005
- **driftguard**: Engine pipeline (parser→collector→analyzer→scorer→patchgen) + HITL PR remediation → validates REQ-003, REQ-004, REQ-007

---

## Open Questions (from SPEC §9) — Audit Assessment

| Question | Assessment | Recommendation |
|----------|------------|----------------|
| **Severity model granularity** | 4-level is sufficient for v0.1; numeric score adds complexity without clear benefit yet | Decide in implementation plan: 4-level, map to agent budget |
| **Ignore-rule scope** | Exact-match (entity id + field) is sufficient for v0.1; wildcards can be added later | Decide in implementation plan: exact-match only for v0.1 |
| **Probe transport** | RWDN is small (1 host + 3 containers); central-over-SSH is simpler and sufficient | Decide in implementation plan: central-over-SSH for v0.1 |

---

## Forward Audit Verdict

**✅ SPEC RWBP-2026-002 v0.1.0 is internally consistent, actionable, and ready for reverse audit.**

No blocking issues found. The three open questions are correctly flagged and do not prevent proceeding to reverse audit + synthesis. They should be resolved in the implementation plan before TDD begins.

---

## Forward Audit Checklist

- [x] Every REQ has Given/When/Then + measurable acceptance criteria
- [x] All REQs use RFC 2119 keywords correctly (SHALL)
- [x] No implementation details baked into requirements
- [x] ADRs are mutually consistent and support the SPEC
- [x] SPEC aligns with RWBP-2026-001 (core engine)
- [x] SPEC aligns with research corpus (10 reports)
- [x] SPEC aligns with reference projects (tfdrift, driftguard)
- [x] Open questions are explicitly flagged in §9
- [x] Out-of-scope items are clearly bounded (agent, auto-remediation, full watchdog impl)
- [x] Security boundary (emit-untrusted/apply-gated) is a first-class requirement (REQ-007)