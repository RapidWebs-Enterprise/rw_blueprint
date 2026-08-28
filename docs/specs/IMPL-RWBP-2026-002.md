# IMPLEMENTATION PLAN
## rw_blueprint — Reconcile/Probe/Watchdog Layer (RWBP-2026-002)

**PLAN ID:** IMPL-RWBP-2026-002  
**Version:** 1.0.0  
**Status:** Approved  
**Date:** 2026-08-27  
**Author:** Network Systems Specialist  
**Approved By:** Steven (sysop)  
**Related To:** RWBP-2026-002 SPEC, ADRs 0007–0012

---

## 1. Executive Summary

**Purpose:** Implement the inbound "observe" half of `rw_blueprint` — the reconcile/probe/watchdog layer that reads live infrastructure state, compares it against the declared `topology.yaml`, and produces drift reports. This closes the loop between declared intent and actual runtime state.

**Business Value:** Enables drift detection for the RWDN recovery (detecting unplanned services like Ergo IRC, Caddy dual-instance, mesh degradation), provides the data foundation for the future self-healing agent, and makes the source-of-truth engine truly bidirectional.

**Key Stakeholders:** Steven (sysop), contributing agents, future platform agent

**High-Level Timeline:** 2 phases over ~3 implementation sessions
- **Phase A (Pull Loop):** Probes + Reconciler + Drift Report — unblocks drift detection
- **Phase B (Push Loop):** Watchdog emitters — adds near-real-time awareness

**Budget:** Internal effort only; no external costs

---

## 2. Goals and Objectives

### 2.1 Business Goals
- **Goal 1:** Detect infrastructure drift automatically — measurable by: drift report identifies all 3 categories (missing/extra/mismatched) against a known test topology
- **Goal 2:** Provide agent-readable drift data — measurable by: drift report is valid JSON with stable schema, consumable by downstream automation
- **Goal 3:** Establish security boundary — measurable by: zero write paths to `topology.yaml` in the layer; test asserts no mutation

### 2.2 Implementation Objectives
| Objective | Success Metric | Target | Measurement |
|-----------|----------------|--------|-------------|
| Live-state projection schema | Pydantic models validate against topology schema | 100% projection coverage | Schema test suite |
| Probe registry + 5 probes | All probes emit normalized fragments | 5/5 probes working | Integration tests |
| Reconciler (3-way diff) | Produces correct drift report for test cases | 100% accuracy on test fixtures | Unit + property tests |
| Severity + ignore rules | Drift items classified + filterable | 4 severity levels, ignore rules work | Unit tests |
| CLI `reconcile` command | End-to-end: topology.yaml → drift report | Single command, <2s | E2E test |
| Security boundary | No mutation of declared model | Zero write paths | Static analysis + test |

---

## 3. Scope

### 3.1 In Scope
- **Live-state schema** (`src/rw_blueprint/live_state.py`): Pydantic models projecting from topology schema (nodes, services, links only)
- **Probe registry** (`src/rw_blueprint/probes/__init__.py`): In-process `PROBES` dict, uniform invocation
- **5 Probes** (`src/rw_blueprint/probes/*.py`): incus, podman, port, dns, tailscale — read-only, emit fragments
- **Reconciler** (`src/rw_blueprint/reconciler.py`): Pure function `(declared, observed) → DriftReport`
- **Drift report schema** (`src/rw_blueprint/drift.py`): Three-way classification + severity + ignore rules
- **CLI command** (`src/rw_blueprint/cli.py`): `rw-blueprint reconcile` subcommand
- **Tests** (`tests/test_live_state.py`, `tests/test_probes.py`, `tests/test_reconciler.py`, `tests/test_reconcile_cli.py`)
- **Example live-state fixture** (`examples/live_state.json`)

### 3.2 Out of Scope
- **Watchdog emitters** (podman events, incus events, systemd path units) — Phase B, deferred per ADR-009
- **Event ingestion endpoint** — Phase B
- **Real-time live-state updates** — Phase B
- **Agent remediation logic** — P5, separate workstream
- **Rendering backends** (Marrow/Shumoku) — deferred per ADR-002
- **Path validation / input-size guards** — deferred per reverse audit S-1, S-3

### 3.3 Assumptions
- RWDN topology is small (1 host + 3 containers + ~6 services)
- Probes run via SSH/Incus exec from workstation (local transport)
- `topology.yaml` is the single source of truth (git-versioned)
- Python 3.11 + Pydantic v2 + Typer stack (ADR-003)

### 3.4 Constraints
- **Technical:** Must reuse existing `rw_blueprint` stack (uv/ruff/mypy/pytest)
- **Security:** No write API in this layer; drift report is the only output
- **Performance:** Must run on 4GB RAM workstation; no daemons
- **Process:** plan-and-audit MEDIUM — TDD, forward audit re-run

---

## 4. Deliverables

### 4.1 Functional Deliverables

| Deliverable ID | Description | Acceptance Criteria | Owner | Due |
|----------------|-------------|---------------------|-------|-----|
| DEL-001 | Live-state projection schema | All topology entities projected; zones/dependencies excluded; Pydantic v2 strict | Dev | Phase A |
| DEL-002 | Probe registry | `PROBES` dict with 5 entries; uniform `Callable[[], LiveStateFragment]` signature | Dev | Phase A |
| DEL-003 | Incus probe | `incus list --format=json` → nodes fragment | Dev | Phase A |
| DEL-004 | Podman probe | `podman ps --format=json` → services fragment | Dev | Phase A |
| DEL-005 | Port probe | `ss -tlnp` → links fragment | Dev | Phase A |
| DEL-006 | DNS probe | `kdig +short` → DNS health fragment | Dev | Phase A |
| DEL-007 | Tailscale probe | `tailscale status --json` → mesh links fragment | Dev | Phase A |
| DEL-008 | Reconciler | Pure function; 3-way diff; severity; ignore rules; deterministic | Dev | Phase A |
| DEL-009 | Drift report schema | JSON-serializable; stable field names; versioned | Dev | Phase A |
| DEL-010 | CLI `reconcile` command | `rw-blueprint reconcile topology.yaml --live live.json -o drift.json` | Dev | Phase A |
| DEL-011 | Test suite | ≥90% coverage; property tests for reconciler; E2E test | Dev | Phase A |

### 4.2 Non-Functional Deliverables

| Deliverable ID | Description | Acceptance Criteria | Owner | Due |
|----------------|-------------|---------------------|-------|-----|
| DOC-001 | Probe authoring guide | `docs/guides/probe-authoring.md` | Dev | Phase A |
| DOC-002 | Drift report schema doc | `docs/api/drift-report.md` | Dev | Phase A |
| CFG-001 | Ignore rules example | `examples/ignore_rules.yaml` | Dev | Phase A |

---

## 5. Timeline and Milestones

### 5.1 Project Timeline
- **Project Start:** 2026-08-27 (this session)
- **Phase A Start/End:** 2026-08-27 → 2026-08-28 (est. 2 sessions)
- **Phase B Start/End:** Deferred (separate sign-off)
- **Project End:** Phase A complete + forward audit all-PASS

### 5.2 Key Milestones

| Milestone ID | Description | Target | Owner | Evidence |
|--------------|-------------|--------|-------|----------|
| MS-001 | Live-state schema + tests green | Session 1 | Dev | `pytest tests/test_live_state.py -v` |
| MS-002 | Probe registry + 5 probes + tests green | Session 1 | Dev | `pytest tests/test_probes.py -v` |
| MS-003 | Reconciler + drift report + tests green | Session 2 | Dev | `pytest tests/test_reconciler.py -v` |
| MS-004 | CLI `reconcile` + E2E test green | Session 2 | Dev | `pytest tests/test_reconcile_cli.py -v` |
| MS-005 | Full suite + forward audit all-PASS | Session 2 | Dev | `pytest` + audit re-run |

### 5.3 Phase Breakdown

**Phase A: Pull Loop (Probes + Reconciler)**
- **Objective:** End-to-end drift detection via scheduled pull
- **Duration:** 2 sessions
- **Key Activities:**
  1. Live-state schema (projection from topology)
  2. Probe registry + 5 probes (incus, podman, port, dns, tailscale)
  3. Reconciler (3-way diff, severity, ignore rules)
  4. CLI `reconcile` command
  5. Test suite (unit + property + E2E)
- **Deliverables:** DEL-001 through DEL-011, DOC-001, DOC-002, CFG-001
- **Gate Criteria:** All tests pass; forward audit re-run → all 9 REQs PASS

**Phase B: Push Loop (Watchdogs) — Deferred**
- **Objective:** Near-real-time drift awareness via event emitters
- **Duration:** Separate increment
- **Key Activities:** Watchdog emitters, event ingestion, live-state updates
- **Gate Criteria:** Phase A complete + separate sign-off

---

## 6. Resource Allocation

### 6.1 Personnel Resources
| Role | Name | Allocation | Primary Responsibilities |
|------|------|------------|--------------------------|
| Tech Lead / Dev | Network Systems Specialist | 100% | Architecture, implementation, tests, audits |

### 6.2 Physical Resources
- **Development Environment:** `~/Workspaces/rw_blueprint/` (uv, Python 3.11, ruff, mypy, pytest)
- **Testing Environment:** Same (in-process, no external deps for Phase A)
- **Reference Projects:** `~/.references/tfdrift/`, `~/.references/driftguard/`

---

## 7. Roles and Responsibilities

### 7.1 Core Team (RACI)
| Role | Responsible | Accountable | Consulted | Informed |
|------|-------------|-------------|-----------|----------|
| Tech Lead | All implementation | All deliverables | Steven (sign-off) | — |

### 7.2 Decision-Making Authority
- **Technical Decisions:** Tech Lead (within SPEC/ADR bounds)
- **Scope Changes:** Steven (sign-off required)
- **Go/No-Go:** Steven (at each milestone)

---

## 8. Risk Management

### 8.1 Risk Register

| Risk ID | Description | Prob | Impact | Score | Mitigation | Owner | Status |
|---------|-------------|------|--------|-------|------------|-------|--------|
| RISK-001 | Probe command failures (SSH/Incus exec) | M | H | 6 | Graceful degradation; partial live state; clear error in fragment | Dev | Open |
| RISK-002 | Live-state schema drift from topology schema | L | H | 3 | Projection is mechanical; test asserts projection validity | Dev | Open |
| RISK-003 | Severity misclassification in reconciler | M | M | 4 | Clear definitions + property tests + ignore rules | Dev | Open |
| RISK-004 | Performance on 4GB RAM | L | H | 3 | In-process, no daemons; probes are lightweight | Dev | Open |
| RISK-005 | Scope creep to push/watchdogs | M | M | 4 | ADR-009 explicitly defers; plan phases enforce | Dev | Open |

### 8.2 Risk Monitoring
- **Review Frequency:** At each milestone (MS-001 through MS-005)
- **Escalation Threshold:** Any risk score ≥6 or new High prob/impact
- **Mitigation Verification:** Test coverage for each risk area

---

## 9. Dependencies

### 9.1 Internal Dependencies
| Dependency ID | Description | Owner | Required By | Status |
|---------------|-------------|-------|-------------|--------|
| DEP-001 | Core engine (RWBP-2026-001) — schema, CLI, generator | Dev | Phase A | ✅ Complete |
| DEP-002 | Topology schema (Zone, Node, Service, Link, Dependency) | Dev | Phase A | ✅ Complete |

### 9.2 External Dependencies
| Dependency ID | Description | Provider | Required By | Status |
|---------------|-------------|----------|-------------|--------|
| DEP-003 | `incus` CLI on workstation | System | Incus probe | ✅ Available |
| DEP-004 | `podman` CLI on workstation | System | Podman probe | ✅ Available |
| DEP-005 | `ss` (iproute2) on workstation | System | Port probe | ✅ Available |
| DEP-006 | `kdig` (knot-dnsutils) on workstation | System | DNS probe | ✅ Available |
| DEP-007 | `tailscale` CLI on workstation | System | Tailscale probe | ✅ Available |

### 9.3 Cross-Dependencies
| Dependent ID | Description | Owner | Dependent On | Status |
|--------------|-------------|-------|--------------|--------|
| DEP-008 | Self-healing agent (P5) | Future | Drift report schema | Planned |
| DEP-009 | RWDN Recovery Roadmap P4 (Observe) | Network Spec | Reconcile layer | Planned |

---

## 10. Quality Gates and Acceptance Criteria

### 10.1 Definition of Done (DoD)
- [ ] Code written and reviewed (self-review per plan-and-audit)
- [ ] Unit tests written and passing (≥90% coverage)
- [ ] Property tests for reconciler (hypothesis-style)
- [ ] E2E test for CLI `reconcile` command
- [ ] Code merged to main branch
- [ ] Documentation updated (probe guide, drift report schema)
- [ ] Forward audit re-run → all 9 REQs PASS
- [ ] All quality gates green (ruff, mypy, pytest)

### 10.2 Quality Gates

| Gate ID | Description | Criteria | Owner | Timing |
|---------|-------------|----------|-------|--------|
| QG-001 | Schema Complete | Live-state models validate; projection test passes | Dev | MS-001 |
| QG-002 | Probes Complete | 5 probes emit valid fragments; registry works | Dev | MS-002 |
| QG-003 | Reconciler Complete | 3-way diff correct; severity + ignore rules work | Dev | MS-003 |
| QG-004 | CLI Complete | `reconcile` command works end-to-end | Dev | MS-004 |
| QG-005 | Full Suite Green | All tests pass; coverage ≥90%; ruff/mypy clean | Dev | MS-005 |
| QG-006 | Forward Audit | All 9 REQs traceable and PASS | Dev | MS-005 |

### 10.3 Acceptance Criteria

**Functional:**
- `rw-blueprint reconcile examples/topology.yaml --live examples/live_state.json -o /tmp/drift.json` produces valid drift report
- Drift report correctly identifies missing/extra/mismatched for test fixtures
- Severity classification matches definitions (critical/high/medium/low/info)
- Ignore rules filter drift items by path pattern

**Performance:**
- Full reconcile <2s for RWDN-scale topology (≤10 nodes, ≤20 services)
- Memory <100MB RSS

**Reliability:**
- Probe failures don't crash reconciler; partial live state emitted
- Deterministic output for same inputs (REQ-008)

**Security:**
- Zero write paths to `topology.yaml` in layer (tested)
- Probes are read-only by construction (no mutating commands)

**Operational:**
- Clear error messages for probe failures
- Drift report is JSON with stable schema (versioned)

---

## 11. Deployment and Release Strategy

### 11.1 Deployment Approach
- **Environment Strategy:** Single environment (workstation) — no staging needed for CLI tool
- **Deployment Method:** `uv sync` + `uv run rw-blueprint` (no install required)
- **Rollback Plan:** `git revert` — single commit per phase

### 11.2 Release Management
- **Release Strategy:** Feature-complete commits to `main`; tagged releases for milestones
- **Communication Plan:** SESSION_STATE.md updated; commit messages conventional

---

## 12. Monitoring and Support

### 12.1 Monitoring Strategy
- **Health Checks:** CLI `--help` works; `validate` still works; `generate` still works
- **Performance Metrics:** Reconcile latency logged in E2E test

### 12.2 Support Model
- **Support Level:** Internal (agent-maintained)
- **Escalation Path:** SESSION_STATE.md → Steven

---

## 13. Appendix

### 13.1 Glossary
- **Declared State:** `topology.yaml` — the git-versioned source of truth
- **Live State:** Observed fragments from probes — normalized to live-state schema
- **Drift Report:** Three-way diff (missing/extra/mismatched) + severity + ignore rules
- **Projection:** Mechanical derivation of live-state schema from topology schema
- **Pull Loop:** Scheduled probe collection + reconciliation
- **Push Loop:** Event-driven watchdog emitters (Phase B)

### 13.2 References
- RWBP-2026-002 SPEC (`docs/specs/RWBP-2026-002.SPEC.md`)
- ADRs 0007–0012 (`docs/adrs/`)
- Forward/Reverse Audits (`docs/specs/audits/`)
- tfdrift reference (`~/.references/tfdrift/`)
- driftguard reference (`~/.references/driftguard/`)

### 13.3 Change Log
| Version | Date | Author | Changes | Approved By |
|---------|------|--------|---------|-------------|
| 1.0.0 | 2026-08-27 | Network Systems Specialist | Initial version | Steven |

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
- [x] Avoids vague terms; includes specific dates, owners, measurable criteria