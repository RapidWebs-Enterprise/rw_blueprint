# ARCHITECTURE DECISION RECORD
## Industry Standard Format for ADRs (2026)

## Document Identification
- **ADR ID**: 009
- **Title**: Pull-first sequencing — build collectors before watchdogs
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

- **Problem Statement**: The full loop has two halves — pull (collectors that poll live
  state) and push (watchdogs that emit events). Building both at once risks over-committing
  to the more complex, more security-sensitive push side before the pull/reconcile contract
  is proven.
- **Drivers**: The research (Event_Driven_Watchdog Push Architecture; Kubernetes controller
  model) found that pull is the reconciliation *baseline* and push is an *optimization* —
  the Kubernetes "watch is an optimization" principle. Pull alone catches drift that
  happened while nobody was watching; push adds near-real-time awareness.
- **Assumptions**: The RWDN is small (one host + three containers + ~6 services); a
  scheduled pull loop is sufficient to catch drift in a timely manner.
- **Constraints**: The watchdog *contract* must be defined now (so the pull side does not
  paint us into a corner), but the watchdog *implementation* can be deferred.

## 2. Decision

- **Decision Statement**: Sequence the work **pull-first**: implement the probe registry
  (collectors) and the reconciler first, prove the drift-detection loop end-to-end, then
  implement watchdogs as a later increment. Define the watchdog event *contract* now, but
  defer the push *emitters*.
- **Considered Alternatives**:
  - **Alternative 1 — Build pull and push together**:
    - **Pros**: Full loop in one increment.
    - **Cons**: Push is the most complex and security-sensitive part; building it before
      the contract is proven risks rework and expands the attack surface prematurely.
  - **Alternative 2 — Push-first**:
    - **Pros**: Real-time awareness from day one.
    - **Cons**: Misses anything that changed before the watchdog was installed; requires
      running emitters on hosts (security surface) before the baseline exists.
- **Decision Rationale**: Pull is read-only, safe, and catches ~90% of drift; it proves the
  contract before we invest in the riskier push side.
- **Implementation Approach**: Phase A = probes + reconciler + drift report. Phase B =
  watchdog emitters consuming the already-defined event contract.

## 3. Status
Accepted.

## 4. Consequences

### 4.1 Positive Consequences
- Lower risk: read-only pull loop first.
- Contract proven before push investment.
- Smaller, reviewable increments.

### 4.2 Negative Consequences
- No near-real-time drift detection until Phase B. Mitigation: scheduled pull loop at a
  heartbeat cadence is sufficient for the RWDN's size.

### 4.3 Neutral Consequences
- The event contract is defined but not yet exercised.

## 5. Implications

### 5.1 Architectural Implications
The watchdog contract is a stable interface even though its implementation is deferred.

### 5.2 Technical Implications
Probe registry and reconciler are the near-term deliverables.

### 5.3 Organizational Implications
None.

### 5.4 Financial Implications
None.

### 5.5 Schedule Implications
Two-phase delivery; Phase A unblocks drift detection sooner.

## 6. Related Documents
- **Supersedes**: None
- **Superseded By**: None
- **Related To**: ADR-008 (classification), ADR-010 (probe registry), ADR-011 (security
  boundary)
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