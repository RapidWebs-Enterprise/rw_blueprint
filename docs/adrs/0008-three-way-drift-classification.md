# ARCHITECTURE DECISION RECORD
## Industry Standard Format for ADRs (2026)

## Document Identification
- **ADR ID**: 008
- **Title**: Three-way drift classification (missing / extra / mismatched) with severity
- **Status**: Accepted
- **Date**: 2026-08-27
- **Author**: Network Systems Specialist
- **Stakeholders**: Steven (sysop)

## Table of Contents
1. [Context](#1-context)
2. [Decision](#2-decision)
3. [Status](#3-status)
4. [Consequences](#4-consequences)
5. [Implications](#5-implications)
6. [Related Documents](#6-related-documents)

---

## 1. Context

- **Problem Statement**: The reconciler must report drift in a way that is both
  mechanically complete and actionable by an agent. A flat "things differ" list is not
  enough — the agent needs to know *what kind* of drift (something missing, something
  unplanned, something changed) and *how urgent* it is.
- **Drivers**: The research (Declared_vs_Actual Reconciliation Control Loop Patterns) found
  the three-way classification — missing / extra / mismatched — is universal across all
  drift tools (driftctl, tfdrift, driftguard). Severity is needed to prioritize remediation
  and to feed the agent's bounded-autonomy budget.
- **Assumptions**: The declared model is the authority; observed state is evidence.
- **Constraints**: The classification must be derivable from the projection schema (ADR-007)
  with no additional input.

## 2. Decision

- **Decision Statement**: Classify every drift finding into exactly one of three categories
  — **missing** (declared but not observed), **extra** (observed but not declared), or
  **mismatched** (both present but differing on a shared field) — and assign each finding a
  severity level (`critical`/`high`/`medium`/`low`) derived from the entity's role and the
  nature of the drift.
- **Considered Alternatives**:
  - **Alternative 1 — Binary (drift / no-drift)**:
    - **Pros**: Simplest.
    - **Cons**: Cannot distinguish "service died" from "unplanned service appeared" from
      "port changed"; useless for prioritization.
  - **Alternative 2 — Rich diff (full field-level patch)**:
    - **Pros**: Maximum detail.
    - **Cons**: Overkill for v0.1; the agent needs classification + severity first, not a
      raw patch.
- **Decision Rationale**: Three-way classification is the proven universal contract, and
  severity is the minimal signal the agent needs to budget its autonomy.
- **Implementation Approach**: The reconciler matches declared vs. observed on `id`, then
  classifies: declared-only → `missing`; observed-only → `extra`; both → field diff →
  `mismatched`. Severity is a pure function of (entity kind, drift category, field).
  **Severity model is 4-level (`critical`/`high`/`medium`/`low`) for v0.1. Agent's
  bounded-autonomy budget maps: `critical` → immediate HITL, `high` → next heartbeat,
  `medium` → next cycle, `low` → log only.**

## 3. Status
Accepted.

## 4. Consequences

### 4.1 Positive Consequences
- Mechanically complete: every difference falls into exactly one bucket.
- Agent can prioritize (severity) and route (category).
- Matches the ecosystem's proven contract.

### 4.2 Negative Consequences
- Severity model is a heuristic; may need tuning as the agent matures. Mitigation: severity
  is a pure, isolated function, easy to adjust.

### 4.3 Neutral Consequences
- Contributors must understand the three categories.

## 5. Implications

### 5.1 Architectural Implications
The drift report is the stable output contract consumed by the agent.

### 5.2 Technical Implications
A `classify` stage in the reconciler; a `severity` function.

### 5.3 Organizational Implications
None.

### 5.4 Financial Implications
None.

### 5.5 Schedule Implications
None material.

## 6. Related Documents
- **Supersedes**: None
- **Superseded By**: None
- **Related To**: ADR-007 (projection), ADR-009 (pull-first)
- **Amends**: None
- **Referenced By**: RWBP-2026-002 SPEC

---

## ADR Quality Checklist
- [x] Title clearly describes the decision
- [x] Context provides sufficient background to understand the problem
- [x] Decision statement is clear and unambiguous
- [x] Alternatives are reasonably considered with pros/cons
- [x] Rationale explains why this decision was chosen
- [x] Status accurately reflects current state
- [x] Consequences are balanced and realistic
- [x] Implications consider broader impacts beyond immediate technical concerns
- [x] Related documents are properly linked
- [x] Language is clear, concise, and free of jargon where possible
- [x] Decision focuses on "what" and "why", not just "how"
- [x] Timeboxed where appropriate