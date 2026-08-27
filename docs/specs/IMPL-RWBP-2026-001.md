# IMPLEMENTATION PLAN
## Industry Standard Format for Software Implementation Plans (2026)

## Document Identification
- **PLAN ID**: IMPL-RWBP-2026-001
- **Version**: 1.0.0
- **Status**: Draft
- **Date**: 2026-08-27
- **Author**: Network Systems Specialist (RapidWebs)
- **Approved By**: Steven (sysop) — pending
- **Related Epic/Feature**: RWBP-2026-001 (rw_blueprint source-of-truth engine)

## Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Goals and Objectives](#2-goals-and-objectives)
3. [Scope](#3-scope)
4. [Deliverables](#4-deliverables)
5. [Timeline and Milestones](#5-timeline-and-milestones)
6. [Resource Allocation](#6-resource-allocation)
7. [Roles and Responsibilities](#7-roles-and-responsibilities)
8. [Risk Management](#8-risk-management)
9. [Dependencies](#9-dependencies)
10. [Quality Gates and Acceptance Criteria](#10-quality-gates-and-acceptance-criteria)
11. [Deployment and Release Strategy](#11-deployment-and-release-strategy)
12. [Monitoring and Support](#12-monitoring-and-support)
13. [Appendix](#13-appendix)

---

## 1. Executive Summary

- **Purpose**: Bring the `rw_blueprint` implementation into full conformance with the
  ratified v2 SPEC (RWBP-2026-001 v0.2.0) and ADRs (0001–0006), closing every finding
  surfaced by the forward and reverse audits.
- **Business Value**: A correct, tested, deterministic source-of-truth engine is the
  foundation for the RWDN recovery (reproducibility) and the future self-healing agent
  (objective reality). Closing the audit backlog removes the drift-class bugs the project
  exists to eliminate.
- **Key Stakeholders**: Steven (sysop), contributing agents.
- **High-Level Timeline**: Single workstream, ordered by dependency (schema → generator →
  tests → docs). No external dependencies; estimated 1–2 focused sessions.
- **Budget Summary**: No financial cost (local CLI, MIT, open toolchain).

## 2. Goals and Objectives

### 2.1 Business Goals
- **Goal 1**: A source-of-truth engine whose schema and generators are provably correct
  against the ratified contract (no silent drift, no placeholder IaC).
- **Goal 2**: A codebase that passes its own quality gates (ruff/mypy/pytest ≥80% coverage)
  and can be handed to any contributing agent with confidence.

### 2.2 Implementation Objectives
- **Objective 1**: Close all High/Medium audit findings (G-1, G-2, G-3, G-4, G-5, G-6).
  - **Success Metric**: Each finding has a passing test or a ratified out-of-scope note.
  - **Target Value**: 6/6 High+Medium findings resolved.
  - **Measurement Method**: `pytest` + audit trace re-run.
- **Objective 2**: Achieve full requirement coverage (REQ-001 through REQ-009).
  - **Success Metric**: Every REQ has implementation + test.
  - **Target Value**: 9/9 REQs PASS.
  - **Measurement Method**: Forward-audit trace table updated to all-PASS.
- **Objective 3**: Eliminate placeholder IaC (G-6, G-7).
  - **Success Metric**: Generated quadlet/Incus artifacts are deployable or explicitly
    documented as skeletons.
  - **Target Value**: No `REPLACE_ME` literal in output.
  - **Measurement Method**: Generated-artifact inspection.

## 3. Scope

### 3.1 In Scope
- **Features/Components**: Schema promotion of `Dependency` to first-class entity;
  `schema_version` enforcement; structured `Port` model; `kind` enum; `image` field on
  `Service`; Incus profile fields (cpu/memory/nic) on `Node`.
- **Integrations**: None external.
- **Data Migrations**: Update `examples/topology.yaml` to the v2 schema.
- **Infrastructure Changes**: None (local CLI only).

### 3.2 Out of Scope
- **Rendering backends** (Marrow/Shumoku/TopoViewer) — deferred per ADR-002.
- **The autonomous agent** — separate workstream (RWDN Recovery Roadmap P5).
- **Live drift detection** — later phase (P4 Observe).
- **Path validation / input size guards** (S-1, S-3) — deferred to the P5 agent phase where
  the model becomes an agent-facing input; documented, not implemented now.
- **Full container-image resolution** — `image` is a reference string; no pull/verify.

### 3.3 Assumptions
- Python 3.11+ and `uv` are available (verified 2026-08-27).
- The topology remains small-to-medium (≤ 100 entities for the near term).
- The v2 SPEC/ADR decisions (dependencies first-class, structured ports, directed links)
  are ratified and stable.

### 3.4 Constraints
- **Time Constraints**: None hard; ordered by dependency.
- **Resource Constraints**: 4GB RAM workstation — run targeted tests, not full suite, unless
  otherwise requested.
- **Technical Constraints**: Determinism (no timestamps/ambient state); no secrets in model
  or output; MIT license.
- **Regulatory Constraints**: None.

## 4. Deliverables

### 4.1 Functional Deliverables
| Deliverable ID | Description | Acceptance Criteria | Owner | Due Date |
|----------------|-------------|---------------------|-------|----------|
| DEL-001 | `Dependency` first-class entity (REQ-001, G-1) | `Dependency` model with `id`/`from`/`to`/`type`; referential integrity enforced; test passes | NSS | 2026-08-27 |
| DEL-002 | `schema_version` enforcement (REQ-008, G-1) | Unsupported version rejected with descriptive error; test passes | NSS | 2026-08-27 |
| DEL-003 | Structured `Port` model (REQ-009, G-5) | `{port, public?, protocol?}` with defaults; quadlet emits correct `PublishPort`; test passes | NSS | 2026-08-27 |
| DEL-004 | `kind` enum + `image` field (G-4, G-6) | `kind` constrained to `Literal`; `image` emitted in quadlet (no `REPLACE_ME`); tests pass | NSS | 2026-08-27 |
| DEL-005 | Incus profile fields (G-7) | `Node` gains cpu/memory/nic; profile emits them; test passes | NSS | 2026-08-27 |

### 4.2 Non-Functional Deliverables
| Deliverable ID | Description | Acceptance Criteria | Owner | Due Date |
|----------------|-------------|---------------------|-------|----------|
| DOC-001 | Round-trip test (G-2) | `parse → dump → parse` lossless; test passes | NSS | 2026-08-27 |
| DOC-002 | No-secret assertion (G-3) | Generated output contains no secret-like patterns; test passes | NSS | 2026-08-27 |
| DOC-003 | Test-coverage closure (T-1, T-4, T-5, T-6) | Duplicate-id (all types), schema_version, empty/non-YAML input, CLI exit codes all tested | NSS | 2026-08-27 |

## 5. Timeline and Milestones

### 5.1 Project Timeline
- **Project Start**: 2026-08-27
- **Phase 1 (Schema) Start/End**: 2026-08-27
- **Phase 2 (Generator) Start/End**: 2026-08-27
- **Phase 3 (Tests/Docs) Start/End**: 2026-08-27
- **Project End**: 2026-08-27 (single focused workstream)

### 5.2 Key Milestones
| Milestone ID | Description | Target Date | Owner | Evidence of Completion |
|--------------|-------------|-------------|-------|------------------------|
| MS-001 | Schema conforms to v2 (five entities, structured ports, version enforcement) | 2026-08-27 | NSS | `pytest tests/test_schema.py` green |
| MS-002 | Generator emits deployable IaC (no placeholders) | 2026-08-27 | NSS | `pytest tests/test_generator.py` green + artifact inspection |
| MS-003 | Full quality gate green | 2026-08-27 | NSS | ruff/mypy/pytest all pass, coverage ≥80% |

### 5.3 Phase Breakdown

**Phase 1: Schema conformance**
- **Objective**: Promote `Dependency`, enforce `schema_version`, add structured `Port`,
  `kind` enum, `image` field, and `Node` resource fields.
- **Duration**: 2026-08-27
- **Key Activities**: Edit `schema.py`; update `examples/topology.yaml`; update
  `tests/test_schema.py`.
- **Deliverables**: DEL-001, DEL-002, DEL-003, DEL-004, DEL-005.
- **Gate Criteria**: `pytest tests/test_schema.py` green; mypy strict clean.

**Phase 2: Generator conformance**
- **Objective**: Emit `image`, structured `PublishPort`, and Incus resource fields; remove
  all `REPLACE_ME` placeholders.
- **Duration**: 2026-08-27
- **Key Activities**: Edit `generator.py` + 4 Jinja2 templates; update
  `tests/test_generator.py`.
- **Deliverables**: DEL-004, DEL-005 (generator half).
- **Gate Criteria**: `pytest tests/test_generator.py` green; generated artifacts inspected
  for correctness.

**Phase 3: Test & doc closure**
- **Objective**: Add round-trip, no-secret, and coverage-gap tests; re-run forward audit to
  all-PASS.
- **Duration**: 2026-08-27
- **Key Activities**: Add tests (DOC-001, DOC-002, DOC-003); update forward-audit trace.
- **Deliverables**: DOC-001, DOC-002, DOC-003.
- **Gate Criteria**: Full `ruff check`/`ruff format --check`/`mypy`/`pytest` green; coverage
  ≥80%.

## 6. Resource Allocation

### 6.1 Personnel Resources
| Role | Name | Allocation (%) | Primary Responsibilities |
|------|------|----------------|--------------------------|
| Architect/Developer | Network Systems Specialist | 100% | Schema, generator, tests |
| Product Owner | Steven | Review | Sign-off, decision ratification |

### 6.2 Budget Resources
| Category | Amount | Description |
|----------|--------|-------------|
| Personnel | $0 | Internal |
| Infrastructure | $0 | Local workstation |
| Licenses | $0 | MIT / open toolchain |
| Training | $0 | N/A |
| Contingency | $0 | N/A |
| **Total** | **$0** |  |

### 6.3 Physical Resources
- **Development Environment**: `rw-workstation-01` (4GB RAM), `uv` + Python 3.11.
- **Testing Environment**: Same (local `pytest`).
- **Staging Environment**: N/A.
- **Production Environment**: N/A (CLI tool; eventual install on infra via `uv`).

## 7. Roles and Responsibilities

### 7.1 Core Team Responsibilities
| Role | Responsible For | Accountable For | Consulted With | Informed Of |
|------|-----------------|-----------------|----------------|-------------|
| Network Systems Specialist | Implementation, tests, audits | Correctness vs. v2 contract | Steven | Steven |
| Steven (Product Owner) | Requirements, sign-off | Scope + decision ratification | NSS | NSS |

### 7.2 Decision-Making Authority
- **Technical Decisions**: Network Systems Specialist (within ratified SPEC/ADR).
- **Scope Changes**: Steven.
- **Resource Allocation**: Steven.
- **Go/No-Go Decisions**: Steven.
- **Issue Escalation**: NSS → Steven.

## 8. Risk Management

### 8.1 Risk Register
| Risk ID | Description | Probability | Impact | Score | Mitigation Strategy | Owner | Status |
|---------|-------------|-------------|--------|-------|---------------------|-------|--------|
| RISK-001 | Schema change breaks existing example/tests | M | L | M-L | Update example + tests in lockstep; run targeted tests after each edit | NSS | Open |
| RISK-002 | Scope creep into agent/rendering work | M | M | M-M | Explicit out-of-scope list (§3.2); defer S-1/S-3 to P5 | NSS | Open |
| RISK-003 | Placeholder IaC remains (G-6/G-7) | L | M | L-M | `image` field + Incus resource fields; artifact inspection gate | NSS | Open |

### 8.2 Risk Monitoring
- **Review Frequency**: Per-phase gate.
- **Escalation Threshold**: Any High-severity finding unresolved.
- **Mitigation Verification**: Re-run forward audit at Phase 3 gate.
- **Contingency Triggers**: Test failure after 3 fix attempts → halt + escalate.

## 9. Dependencies

### 9.1 Internal Dependencies
| Dependency ID | Description | Owner | Required By | Provided By | Status |
|---------------|-------------|-------|-------------|-------------|--------|
| DEP-001 | Ratified v2 SPEC + ADRs | Steven | Phase 1 | NSS | Done |

### 9.2 External Dependencies
None.

### 9.3 Cross-Dependencies
| Dependent ID | Description | Owner | Dependent On | Status |
|--------------|-------------|-------|--------------|--------|
| DEP-002 | RWDN Recovery Roadmap P2 (reproducibility) | Steven | This engine | Pending |
| DEP-003 | Self-healing agent (P5) | Steven | This engine | Pending |

## 10. Quality Gates and Acceptance Criteria

### 10.1 Definition of Done (DoD)
- [ ] Code written and reviewed
- [ ] Unit tests written and passing (≥80% coverage)
- [ ] `ruff check` + `ruff format --check` clean
- [ ] `mypy` (strict) clean
- [ ] `pytest` green
- [ ] Forward-audit trace updated to all-PASS
- [ ] No `REPLACE_ME` placeholder in generated output

### 10.2 Quality Gates
| Gate ID | Description | Criteria | Owner | Timing |
|---------|-------------|----------|-------|--------|
| QG-001 | Schema conformance | `test_schema.py` green + mypy clean | NSS | End Phase 1 |
| QG-002 | Generator conformance | `test_generator.py` green + artifact inspection | NSS | End Phase 2 |
| QG-003 | Full gate | ruff/mypy/pytest green, coverage ≥80% | NSS | End Phase 3 |

### 10.3 Acceptance Criteria
- **Functional Acceptance**: All 9 REQs PASS (forward-audit trace).
- **Performance Acceptance**: `validate`/`generate` < 1s for ≤100 entities.
- **Reliability Acceptance**: Invalid input → descriptive error, no crash/partial output.
- **Security Acceptance**: No secrets in model or output (DOC-002 test).
- **Usability Acceptance**: Two commands (`validate`, `generate`) suffice.
- **Operational Acceptance**: Installable via `uv`; deterministic output.

## 11. Deployment and Release Strategy

### 11.1 Deployment Approach
- **Environment Strategy**: Local dev only (no staging/prod for a CLI).
- **Deployment Method**: `uv sync` / `pip install -e .`.
- **Rollback Plan**: Git revert (single branch, conventional commits).
- **Data Migration Strategy**: Update `examples/topology.yaml` to v2 schema in-place.

### 11.2 Release Management
- **Release Strategy**: Single v0.2.0 tag once gates green.
- **Communication Plan**: Update `docs/SESSION_STATE.md`.
- **Training Plan**: N/A.
- **Support Plan**: N/A (internal tool).

### 11.3 Deployment Checklist
- [ ] All tests passing
- [ ] ruff/mypy clean
- [ ] Coverage ≥80%
- [ ] Example topology updated to v2
- [ ] SESSION_STATE.md updated

## 12. Monitoring and Support

### 12.1 Monitoring Strategy
- **Health Checks**: CI workflow (ruff/mypy/pytest) on push.
- **Performance Metrics**: N/A (CLI).
- **Business Metrics**: N/A.
- **Alerting**: N/A.
- **Logging**: Descriptive validation errors.

### 12.2 Support Model
- **Support Levels**: Single (NSS).
- **Support Hours**: On-demand.
- **Escalation Path**: NSS → Steven.
- **Knowledge Base**: `docs/` (SPEC, ADRs, research, audits).
- **Feedback Mechanism**: Direct to Steven.

### 12.3 Post-Implementation Review
- **Review Timing**: After Phase 3 gate.
- **Review Criteria**: All findings closed; forward audit all-PASS.
- **Success Metrics**: 9/9 REQs PASS; 0 placeholders; gates green.
- **Lessons Learned**: Recorded in SESSION_STATE.md.
- **Action Items**: Deferred S-1/S-3 → P5 agent phase.

## 13. Appendix

### 13.1 Glossary
| Term | Definition |
|------|------------|
| NSS | Network Systems Specialist |
| SoT | Source of Truth |
| IaC | Infrastructure as Code |
| Quadlet | systemd-native declarative podman container units |

### 13.2 References
- `docs/specs/RWBP-2026-001.SPEC.md` (v0.2.0)
- `docs/adrs/0001`–`0006`
- `docs/specs/audits/forward-audit-RWBP-2026-001.md`
- `docs/specs/audits/reverse-audit-RWBP-2026-001.md`

### 13.3 Change Log
| Version | Date | Author | Changes | Approved By |
|---------|------|--------|---------|-------------|
| 1.0.0   | 2026-08-27 | Network Systems Specialist | Initial version | Pending |

### 13.4 Approval Signatures
| Role | Name | Signature | Date |
|------|------|-----------|------|
| Project Sponsor | Steven | | |
| Product Owner | Steven | | |
| Project Manager | NSS | | |
| Technical Lead | NSS | | |
| QA Lead | NSS | | |
| Operations Lead | NSS | | |

---

## Implementation Plan Quality Checklist
- [x] Clear, measurable goals and objectives
- [x] Well-defined scope with explicit in/out of scope items
- [x] Realistic timeline with meaningful milestones
- [x] Adequate resource allocation (people, budget, equipment)
- [x] Clear roles and responsibilities (RACI where appropriate)
- [x] Comprehensive risk identification with mitigation strategies
- [x] All dependencies identified and tracked
- [x] Quality gates and acceptance criteria defined
- [x] Deployment/release strategy well thought out
- [x] Monitoring and support plans in place
- [x] Post-implementation review planned
- [x] Written in clear, concise language
- [x] Avoids vague terms like "soon" or "as needed"
- [x] Includes specific dates, owners, and measurable criteria