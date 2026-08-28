# IMPLEMENTATION PLAN
## rw_blueprint — MCP + JSON/Exit-Codes + Remediation (RWBP-2026-003)

**PLAN ID:** IMPL-RWBP-2026-003
**Version:** 1.0.0
**Status:** Draft (awaiting sign-off)
**Date:** 2026-08-28
**Author:** Network Systems Specialist
**Approved By:** (pending)
**Related To:** RWBP-2026-003 SPEC v0.2.0, ADRs 0013/0015/0017/0011/0018

---

## 1. Executive Summary

**Purpose:** Implement the "now" tier of `rw_blueprint` — an MCP server exposing the four
verbs as typed, approval-gated tools; a deterministic, versioned JSON drift report with a
`0/1/2` exit-code contract; and a minimal, never-auto-applied remediation proposal. This
closes the observe→propose half of the self-healing loop without weakening the
apply-is-gated boundary.

**Business Value:** Makes the tool agent-consumable (not just human-CLI), makes drift
detection a CI gate, and gives the P5 agent a machine-parseable report + proposal instead
of prose.

**Key Stakeholders:** Steven (sysop), contributing agents, future platform agent.

**High-Level Timeline:** 3 implementation phases over ~2 sessions.
- **Phase 1 (Report + Exit Codes):** typed JSON serialization + `0/1/2` contract
- **Phase 2 (Remediation):** JSON-Patch proposal + blast radius
- **Phase 3 (MCP):** FastMCP server + registration smoke test

**Budget:** Internal effort only; one additive dependency (`mcp>=1.27,<2`).

---

## 2. Goals and Objectives

### 2.1 Business Goals
- **Goal 1:** Agents consume the tool as typed tools — measurable by: MCP server registers
  4 tools + 2 resources (REQ-001).
- **Goal 2:** CI can gate on drift — measurable by: exit `0/1/2` contract honored (REQ-005).
- **Goal 3:** Drift reports propose fixes — measurable by: each finding carries a minimal
  JSON Patch + blast radius, never applied (REQ-006).

### 2.2 Implementation Objectives
| Objective | Success Metric | Target | Measurement |
|-----------|----------------|--------|-------------|
| Typed JSON report | Report serializes from a Pydantic model with `report_version` | 100% | Golden-file + round-trip test |
| Exit-code contract | `0`/`1`/`2` correct; errors no longer exit `1` | 3/3 | CLI E2E test |
| Remediation | Minimal JSON Patch per finding, blast radius, non-applied | 100% | Unit + property tests |
| MCP surface | 4 tools + 2 resources, no logic fork, no mutation | 4+2 | Registration smoke + read-only test |

---

## 3. Scope

### 3.1 In Scope
- **Report serialization** (`src/rw_blueprint/report.py`): Pydantic model for `DriftReport`
  with `report_version`; JSON emitter replacing the current `__dict__` dump (`cli.py:188-193`).
- **Exit-code refactor** (`src/rw_blueprint/cli.py`): errors → exit `2`; drift → exit `1`;
  clean → exit `0`; `--fail-on` retained as the threshold (D-05).
- **Remediation** (`src/rw_blueprint/remediation.py`): JSON Patch (RFC 6902) per finding;
  blast radius from declared `topology.dependencies`; direction explicit (D-01/D-02/D-06).
- **MCP server** (`src/rw_blueprint/mcp.py`): FastMCP; 4 tools + 2 resources; no logic fork;
  verb-class annotations (D-07/D-08/D-10).
- **Entry point** (`pyproject.toml`): `rw-blueprint-mcp` console script; `mcp` dependency.
- **Tests** (`tests/test_report.py`, `tests/test_remediation.py`, `tests/test_mcp.py`).

### 3.2 Out of Scope
- Entry-points probe discovery (ADR-014), schema migration (ADR-016), supply-chain
  security (G3), layered config (ADR-018) — all deferred per SPEC §2.2.
- The P5 agent; auto-remediation; watch/wave-3 gaps.

### 3.3 Assumptions
- The four verbs' functions are pure/stateless (RWBP-2026-001/002).
- MCP stdio transport; local host; no network socket.

### 3.4 Constraints
- Reuse `uv`/ruff/mypy/pytest stack; Python 3.11+.
- Emit-untrusted/apply-gated preserved (ADR-011/015).
- Enterprise naming (ADR-018): `rw_blueprint` package, `rw-blueprint-mcp` entry point.

---

## 4. Deliverables

| ID | Description | Acceptance Criteria | Phase |
|----|-------------|---------------------|-------|
| DEL-001 | Typed report model + JSON serialization | Parses from Pydantic; `report_version` present; round-trip lossless | 1 |
| DEL-002 | Exit-code refactor | `0`/`1`/`2` correct; errors → `2` | 1 |
| DEL-003 | Remediation module | Minimal JSON Patch; blast radius; non-applied; direction explicit | 2 |
| DEL-004 | MCP server module | 4 tools + 2 resources; delegates to core; no business logic | 3 |
| DEL-005 | Entry point + dependency | `rw-blueprint-mcp` script; `mcp>=1.27,<2` in `pyproject.toml` | 3 |
| DEL-006 | Test suite | Golden-file determinism; registration smoke; read-only; exit codes | 1–3 |
| DOC-001 | MCP integration guide | `docs/guides/mcp-integration.md` | 3 |
| DOC-002 | JSON report schema doc | `docs/api/report-schema.md` | 1 |

---

## 5. Timeline and Milestones

| Milestone | Description | Evidence |
|-----------|-------------|----------|
| MS-001 | Report + exit codes green | `pytest tests/test_report.py` + CLI E2E exit-code test |
| MS-002 | Remediation green | `pytest tests/test_remediation.py` (minimal-diff + blast-radius) |
| MS-003 | MCP server green | `pytest tests/test_mcp.py` (registration + read-only + no-fork) |
| MS-004 | Full suite + forward audit all-PASS | `pytest` + audit re-run |

**Phase 1** (Report + Exit Codes): DEL-001, DEL-002, DOC-002, part of DEL-006.
**Phase 2** (Remediation): DEL-003, part of DEL-006.
**Phase 3** (MCP): DEL-004, DEL-005, DOC-001, part of DEL-006.

---

## 6. Resource Allocation
- **Dev:** Network Systems Specialist (100%).
- **Environment:** `~/Workspaces/rw_blueprint/` (uv, Python 3.11).
- **References:** `~/.references/tfdrift/`, `~/.references/driftguard/`.

---

## 7. Roles and Responsibilities (RACI)
| Role | Responsible | Accountable | Consulted | Informed |
|------|-------------|-------------|-----------|----------|
| Tech Lead | All implementation | All deliverables | Steven (sign-off) | — |

---

## 8. Risk Management

| Risk ID | Description | Prob | Impact | Score | Mitigation |
|---------|-------------|------|--------|-------|------------|
| RISK-001 | `mcp` 1.x API drift breaks registration | M | M | 4 | Pin `<2`; registration smoke test (D-11) |
| RISK-002 | Exit-code refactor breaks existing `--fail-on` | M | M | 4 | Map threshold→outcome; E2E test each code |
| RISK-003 | Remediation direction wrong (reintroduces drift) | M | H | 6 | Direction explicit; observed-authoritative default (D-06) |
| RISK-004 | JSON serialization regression (drops fields) | L | H | 3 | Round-trip + golden-file tests |
| RISK-005 | MCP tool surfaces a write path | L | H | 3 | Enumerate tools → assert no mutation (REQ-003) |

---

## 9. Dependencies
| ID | Description | Status |
|----|-------------|--------|
| DEP-001 | Core engine (RWBP-2026-001) | ✅ Complete |
| DEP-002 | Reconcile layer (RWBP-2026-002) | ✅ Complete |
| DEP-003 | `mcp` SDK (`>=1.27,<2`) | ⏳ Add in Phase 3 |

---

## 10. Quality Gates and Acceptance Criteria

### 10.1 Definition of Done
- [ ] All 9 REQs pass; `ruff check`/`ruff format --check`/`mypy`/`pytest` green.
- [ ] Coverage ≥ 80%; golden-file byte-determinism test.
- [ ] Forward audit re-run → all 9 REQs PASS.

### 10.2 Quality Gates
| Gate | Criteria | Milestone |
|------|----------|-----------|
| QG-001 | Report round-trips; `report_version` present | MS-001 |
| QG-002 | Exit `0`/`1`/`2` correct | MS-001 |
| QG-003 | Remediation minimal + deterministic + non-applied | MS-002 |
| QG-004 | MCP registers 4+2; no fork; no mutation | MS-003 |
| QG-005 | Full suite green + forward audit all-PASS | MS-004 |

### 10.3 Acceptance Criteria
- `rw-blueprint reconcile ... --format json` emits versioned JSON; exit codes 0/1/2 correct.
- `rw-blueprint-mcp` registers 4 tools + 2 resources; no tool mutates the model.
- Each finding carries a minimal JSON Patch + blast radius; nothing is auto-applied.

---

## 11. Deployment and Release
- **Method:** `uv sync` + `uv run`; `mcp` added to `dependencies`.
- **Rollback:** `git revert` per phase.
- **Release:** single feature-complete commit; conventional message.

---

## 12. Monitoring and Support
- **Health:** `rw-blueprint-mcp` registration smoke test in CI; `validate`/`generate`/`reconcile` still work.
- **Escalation:** SESSION_STATE.md → Steven.

---

## 13. Appendix
### 13.1 References
- RWBP-2026-003 SPEC v0.2.0; ADRs 0011/0013/0015/0017/0018; synthesis + audits.
### 13.2 Change Log
| Version | Date | Author | Changes | Approved By |
|---------|------|--------|---------|-------------|
| 1.0.0 | 2026-08-28 | Network Systems Specialist | Initial version | (pending) |

---

## Implementation Plan Quality Checklist
- [x] Clear, measurable goals and objectives
- [x] Well-defined scope with explicit in/out of scope items
- [x] Realistic timeline with meaningful milestones
- [x] Adequate resource allocation
- [x] Clear roles and responsibilities
- [x] Comprehensive risk identification with mitigation strategies
- [x] All dependencies identified and tracked
- [x] Quality gates and acceptance criteria defined
- [x] Deployment/release strategy well thought out
- [x] Monitoring and support plans in place
- [x] Written in clear, concise language
