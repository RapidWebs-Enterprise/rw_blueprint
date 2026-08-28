# ARCHITECTURE DECISION RECORD
## Industry Standard Format for ADRs (2026)

## Document Identification
- **ADR ID**: 012
- **Title**: Borrow the osquery model, not the osquery tool
- **Status**: Proposed
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

- **Problem Statement**: The probe layer needs a model for observing host state. osquery is
  the canonical tool for this (the OS as a relational database), but adopting it wholesale
  brings a C++ daemon, a SQL engine, an embedded RocksDB store, and a plugin system — far
  heavier than a fleet of ~5 read-only Python probes needs.
- **Drivers**: The research (Host_Introspection Osquery Style Model; Uptycs "in-house vs
  building") found that running osquery in-house requires building fleet management, a data
  pipeline, storage, and visualization around it — "what starts as endpoint visibility
  quickly becomes an infrastructure problem." The *model* (declarative observation, uniform
  output, on-demand generation, event publishers) is the valuable part, not the tool.
- **Assumptions**: The RWDN is small; probes are first-party Python; the reconciler is the
  central consumer.
- **Constraints**: Must stay lightweight (4GB RAM workstation, small fleet); must reuse the
  Python/Pydantic stack (ADR-003).

## 2. Decision

- **Decision Statement**: **Borrow osquery's model, not its tool.** Adopt the four
  transferable principles — (1) declarative observation (describe *what*, not *how*),
  (2) uniform output shape (every probe emits a normalized fragment), (3) on-demand
  generation (probes generate fragments when invoked, no persistent probe-side store), and
  (4) event publishers as the future push/watchdog layer — while implementing probes as
  lightweight first-party Python functions.
- **Considered Alternatives**:
  - **Alternative 1 — Adopt osquery wholesale**:
    - **Pros**: Battle-tested, rich table ecosystem.
    - **Cons**: C++ daemon + SQL engine + RocksDB + plugin system; requires building fleet
      management around it; heavy for a 5-probe fleet.
  - **Alternative 2 — Ad-hoc per-probe scripts (no shared model)**:
    - **Pros**: Minimal upfront design.
    - **Cons**: No uniform output contract; the reconciler must know each probe's
      idiosyncrasies; no path to the push/watchdog layer.
- **Decision Rationale**: The model gives the reconciler a uniform contract and a path to
  the push layer, without the operational weight of the osquery platform.
- **Implementation Approach**: Probes are Python functions returning `live_state` fragments;
  the registry (ADR-010) provides uniform invocation; the event contract (ADR-009) reserves
  the push layer for later.

## 3. Status
Accepted.

## 4. Consequences

### 4.1 Positive Consequences
- Lightweight, auditable, read-only probes.
- Uniform output contract for the reconciler.
- A clear path to the push/watchdog layer (event publishers).

### 4.2 Negative Consequences
- No SQL query interface over host state. Mitigation: not needed — the reconciler consumes
  structured fragments, not ad-hoc queries.

### 4.3 Neutral Consequences
- Probes are first-party and purpose-built for the RWDN.

## 5. Implications

### 5.1 Architectural Implications
The probe model is declarative observation with uniform output; the reconciler is the
central consumer.

### 5.2 Technical Implications
Probes are pure-ish Python functions; no embedded DB, no daemon.

### 5.3 Organizational Implications
None.

### 5.4 Financial Implications
None.

### 5.5 Schedule Implications
None material.

## 6. Related Documents
- **Supersedes**: None
- **Superseded By**: None
- **Related To**: ADR-010 (probe registry), ADR-009 (pull-first)
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