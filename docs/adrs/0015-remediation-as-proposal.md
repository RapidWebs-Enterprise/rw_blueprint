# ARCHITECTURE DECISION RECORD
## Industry Standard Format for ADRs (2026)

## Document Identification
- **ADR ID**: 015
- **Title**: Remediation as a gated proposal, never auto-apply
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

- **Problem Statement**: The reconciler reports drift (missing/extra/mismatched) but
  produces no structured fix. The observe→propose loop is incomplete: an agent (or human)
  sees *what* drifted but not *what to do about it*.
- **Drivers**: The gap-analysis research found every serious remediation tool converges
  on the same shape: gitops-drift-remediation-agent computes **minimal** JSON Patches
  ("smallest possible diff, never full resource replacement") with least-privilege
  (never delete/create) and dry-run default; InfraIgnite ships fixes as reviewable PRs
  with blast radius + cost; the AWS drift-detection sample auto-remediates only low-risk
  drift and routes high-risk to approval. Critically, **OpenSentinel** found LLM-generated
  patches are *structurally valid but sometimes semantically wrong*, empirically mandating
  human review.
- **Assumptions**: The declared model (`topology.yaml`) is the source of truth; applying
  a change to it is consequential and gated by ADR-011.
- **Constraints**: Must not weaken ADR-011 (apply-is-gated); the proposal must be
  deterministic and reviewable, not free-form prose.

## 2. Decision

- **Decision Statement**: The reconciler emits, alongside the drift report, a
  **structured remediation proposal** — per drift item, a minimal, deterministic YAML
  diff (or JSON Patch) that would restore declared/observed agreement, each carrying a
  **blast-radius estimate** and **severity**. The proposal is **never auto-applied**; it
  is the input to the HITL gate (human or gated agent) established by ADR-011.
- **Considered Alternatives**:
  - **Alternative 1 — Auto-apply**:
    - **Pros**: Fully automated self-healing.
    - **Cons**: Violates ADR-011; a wrong observation silently rewrites the source of
      truth; OpenSentinel shows semantic errors are common enough to require review.
  - **Alternative 2 — Report-only (status quo)**:
    - **Pros**: Safest.
    - **Cons**: Leaves the observe→propose loop incomplete; the agent must re-derive the
      fix from prose.
  - **Alternative 3 — LLM-generated prose recommendation**:
    - **Pros**: Human-readable rationale.
    - **Cons**: Non-deterministic, not machine-checkable, and semantically unreliable
      (OpenSentinel finding).
- **Decision Rationale**: A deterministic minimal diff is auditable, reviewable, and
  machine-consumable; blast radius + severity let the gate decide routing (low-risk vs
  HITL) without weakening ADR-011. The fix is *proposed*, not applied.
- **Implementation Approach**: Add a `remediation` module that, for each drift item,
  computes the minimal patch (add/remove/update the declared entity to match the observed
  or vice-versa, depending on drift class), attaches a blast-radius estimate derived from
  the dependency graph, and includes it in the drift report under a `remediation` key.

## 3. Status

Accepted.

## 4. Consequences

### 4.1 Positive Consequences
- Completes the observe→propose loop with a deterministic, reviewable artifact.
- Minimal diff = minimal blast radius (never full-document replacement).
- Blast-radius + severity enable risk-tiered routing to the HITL gate.

### 4.2 Negative Consequences
- Blast-radius estimation is heuristic in v1 (dependency-graph depth/count), not a full
  impact simulation; mitigation: clearly labeled as an estimate.
- Remediation adds schema surface and test surface; mitigation: deterministic diff tests
  + golden files.

### 4.3 Neutral Consequences
- The drift report grows a `remediation` section; the drift classification (ADR-008) is
  unchanged.

## 5. Implications

### 5.1 Architectural Implications
The reconciler's output becomes drift + proposal; apply remains a separate gated action.

### 5.2 Technical Implications
A `remediation` module; a minimal-diff function; blast-radius heuristic; JSON output.

### 5.3 Organizational Implications
The agent (P5) can propose-and-gate rather than re-derive; humans review diffs, not prose.

### 5.4 Financial Implications
None.

### 5.5 Schedule Implications
Moderate; sequenced with the machine-readable-output ADR (ADR-017) and the MCP ADR (ADR-013).

## 6. Related Documents
- **Supersedes**: None
- **Superseded By**: None
- **Related To**: ADR-008 (three-way classification), ADR-011 (apply-is-gated), ADR-017
  (machine-readable report)
- **Amends**: None (extends ADR-011's boundary with the proposal artifact)
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
