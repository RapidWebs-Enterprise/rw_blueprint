# ARCHITECTURE DECISION RECORD
## Industry Standard Format for ADRs (2026)

## Document Identification
- **ADR ID**: 011
- **Title**: Emit-is-untrusted / apply-is-gated security boundary
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

- **Problem Statement**: The reconcile layer observes live state and reports drift. The
  critical security question is: what may a probe or watchdog *do*? If any component can
  write to the declared model, the "source of truth" is no longer trustworthy — a
  compromised or buggy probe could silently rewrite reality.
- **Drivers**: The research (Event_Driven_Watchdog Push Architecture; OpenTelemetry
  agent-vs-gateway) found the canonical boundary: **emitting an observation is untrusted
  and append-only; applying a change is trusted and gated**. Only the gateway tier (the
  reconciler) holds write access to the declared model, and even that is HITL-gated.
- **Assumptions**: Probes and watchdogs run on or near the observed hosts, which are less
  trusted than the declared model's repository.
- **Constraints**: The declared model (`topology.yaml`) is git-versioned and is the single
  source of truth; its integrity is paramount.

## 2. Decision

- **Decision Statement**: Enforce a hard boundary: **probes and watchdogs may only emit
  observations** (append-only, untrusted); **no component in this layer may write to the
  declared model**. The reconciler's only output is the drift report. Applying a change to
  the declared model is a separate, HITL-gated action performed by a human or the (future)
  agent under explicit approval.
- **Considered Alternatives**:
  - **Alternative 1 — Reconciler auto-applies drift**:
    - **Pros**: Fully automated self-healing.
    - **Cons**: A wrong observation (or a compromised probe) would silently rewrite the
      source of truth; violates the "agent is the reward, not a shortcut" principle.
  - **Alternative 2 — Probes write directly to the model**:
    - **Pros**: Simplest data flow.
    - **Cons**: No trust boundary; any probe becomes a write path to reality.
- **Decision Rationale**: The source of truth must be write-protected from the observation
  layer. Emit is cheap and safe; apply is consequential and must be gated.
- **Implementation Approach**: Probes/watchdogs return fragments (no write API). The
  reconciler is a pure function (declared, observed) → drift report. No code path in the
  layer mutates `topology.yaml`.

## 3. Status
Accepted.

## 4. Consequences

### 4.1 Positive Consequences
- The source of truth is write-protected from the observation layer.
- A compromised probe cannot rewrite reality.
- Clear, auditable trust boundary.

### 4.2 Negative Consequences
- Self-healing requires a separate HITL-gated apply step (not automatic). Mitigation: this
  is intentional — the agent's autonomy is bounded by design.

### 4.3 Neutral Consequences
- The drift report is the only artifact the layer produces.

## 5. Implications

### 5.1 Architectural Implications
The boundary is a first-class invariant, enforced by construction and by test.

### 5.2 Technical Implications
No write API in probes/watchdogs; reconciler is pure; a test asserts no mutation.

### 5.3 Organizational Implications
Applying drift is always a human (or gated-agent) action.

### 5.4 Financial Implications
None.

### 5.5 Schedule Implications
None material.

## 6. Related Documents
- **Supersedes**: None
- **Superseded By**: None
- **Related To**: ADR-009 (pull-first), ADR-010 (probe registry)
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