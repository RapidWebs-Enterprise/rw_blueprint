# ARCHITECTURE DECISION RECORD
## Industry Standard Format for ADRs (2026)

## Document Identification
- **ADR ID**: 014
- **Title**: Entry-points probe discovery for third-party extensibility
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

- **Problem Statement**: ADR-010 chose an in-process probe registry over a plugin
  framework, correctly, for the ~5 first-party probes. But "prepare for expansion" (the
  stated requirement) needs a fork-free way for a third party — or future-us — to add a
  probe without editing `rw_blueprint`'s source.
- **Drivers**: The gap-analysis research found `importlib.metadata.entry_points` is the
  stdlib (since Python 3.8, non-provisional since 3.10) canonical "creating and
  discovering plugins" mechanism per the Python Packaging User Guide. Shumoku ships a
  plugin SDK for data-source plugins; click-plugins demonstrates the standard
  `BrokenCommand` pattern so a failing plugin degrades gracefully instead of breaking the
  CLI. `stevedore` is the production-grade wrapper but is overkill here.
- **Assumptions**: The core probe set stays first-party and in-process; third-party
  probes are an *opt-in* expansion, not a near-term need.
- **Constraints**: Must not add a plugin framework dependency; must not weaken the
  read-only-by-construction property (ADR-011); a misbehaving third-party probe must not
  break the core tool.

## 2. Decision

- **Decision Statement**: Keep the in-process registry for the core probes (ADR-010
  unchanged in spirit), and **additionally** discover third-party probes via an
  `rw_blueprint.probes` entry-point group using `importlib.metadata.entry_points`. The
  registry merges in-process probes first, then discovered entry-points, deduplicating by
  name; a probe that fails to load is surfaced as a diagnostic (BrokenCommand-style), never
  a crash.
- **Considered Alternatives**:
  - **Alternative 1 — Full plugin framework (pluggy / stevedore)**:
    - **Pros**: Rich plugin lifecycle, dependency ordering, extension maps.
    - **Cons**: A framework dependency; overkill for the current scale; harder to audit
      the read-only property.
  - **Alternative 2 — In-process only (status quo)**:
    - **Pros**: Simplest; auditable.
    - **Cons**: Third-party probes require forking; forecloses expansion the user
      explicitly asked to enable.
- **Decision Rationale**: Entry points are stdlib, zero-dependency, cross-package, and
  the canonical PyPA mechanism — they give the expansion seam without a framework. The
  in-process registry remains the auditable default; entry-points are an additive layer.
- **Implementation Approach**: Add `entry_points(group="rw_blueprint.probes")` discovery
  to the registry; wrap each load in try/except and register a `BrokenProbe` on failure.
  Document the entry-point contract (a callable returning a `live_state` fragment) in
  `CONTRIBUTING.md`.

## 3. Status

Proposed — awaiting review.

## 4. Consequences

### 4.1 Positive Consequences
- Third-party probes can be installed via `pip` and auto-discovered — no fork, no config.
- Zero framework dependency; stdlib only.
- Core probes remain in-process and auditable.

### 4.2 Negative Consequences
- Discovery order and name-conflict handling become a contract (mitigation: in-process
  wins; conflicts logged).
- A third-party probe executes arbitrary code at discovery time (mitigation: it is the
  installer's trust decision; documented, and failures are isolated).

### 4.3 Neutral Consequences
- The registry API gains an optional discovery pass; the probe *contract* is unchanged.

## 5. Implications

### 5.1 Architectural Implications
The probe registry becomes a merge of static and discovered entries; the contract stays
the same.

### 5.2 Technical Implications
Uses `importlib.metadata.entry_points`; a `BrokenProbe` diagnostic; a documented
entry-point group `rw_blueprint.probes`.

### 5.3 Organizational Implications
Third parties (or future internal teams) can contribute probes as separate packages.

### 5.4 Financial Implications
None.

### 5.5 Schedule Implications
None material; additive.

## 6. Related Documents
- **Supersedes**: None
- **Superseded By**: None
- **Related To**: ADR-010 (in-process registry), ADR-011 (apply-is-gated)
- **Amends**: ADR-010 (adds the entry-points discovery path; does not reverse the
  in-process decision)
- **Referenced By**: Ecosystem_Gap_Analysis research report

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
