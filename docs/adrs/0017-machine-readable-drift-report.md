# ARCHITECTURE DECISION RECORD
## Industry Standard Format for ADRs (2026)

## Document Identification
- **ADR ID**: 017
- **Title**: Machine-readable drift report with deterministic exit codes
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

- **Problem Statement**: The reconciler emits a Rich table — human-only. The P5-agent
  rationale was explicitly "parse a JSON report at a moment's notice", and CI needs to
  gate on drift, but there is no machine-readable output and no exit-code contract.
- **Drivers**: The gap-analysis research found the field has converged on an identical
  contract: kube-diff, kdrift, and BlastRadius all use `--format json` + `--exit-code` /
  `--check` with exit codes `0` = clean, `1` = drift/violation, `2` = error. This is how
  drift detection becomes a pipeline gate rather than a human eyeballing a table.
- **Assumptions**: Both humans (table) and machines/agents/CI (JSON) consume the report;
  the JSON shape must be a stable contract.
- **Constraints**: Must not break the existing Rich table (default human view); JSON must
  be deterministic and versioned.

## 2. Decision

- **Decision Statement**: `reconcile` (and `validate`) emit a **deterministic,
  versioned JSON** report via `--format json`, and return **exit codes `0` (clean),
  `1` (drift/violation), `2` (error)**. The Rich table remains the default human view;
  `--format json` is the machine view. The JSON schema carries a `report_version` field
  so consumers can detect shape changes.
- **Considered Alternatives**:
  - **Alternative 1 — Table-only (status quo)**:
    - **Pros**: Simplest.
    - **Cons**: No machine consumption; no CI gating; the agent must parse ANSI text.
  - **Alternative 2 — JSON-only**:
    - **Pros**: Single output.
    - **Cons**: Regresses the human experience; Rich table is already good.
  - **Alternative 3 — YAML output**:
    - **Pros**: Matches the declared model's format.
    - **Cons**: YAML is not a native agent/CI interchange; JSON is the lingua franca of
      tooling and MCP.
- **Decision Rationale**: Dual output (human default + machine opt-in) serves both
  consumers; deterministic exit codes unlock CI gating, which is the bridge from observe
  (P4) to automate (P5). A versioned JSON schema keeps the contract stable.
- **Implementation Approach**: Add `--format {table,json}` and `--exit-code` (or make
  exit codes unconditional and documented). Serialize the drift report (including the
  ADR-015 remediation proposal) to a Pydantic-derived JSON model with a `report_version`
  field. Add golden-file tests asserting byte-stability.

## 3. Status

Accepted.

## 4. Consequences

### 4.1 Positive Consequences
- CI can gate on drift (`--exit-code` / exit `1`); the agent can parse JSON directly.
- The JSON schema is a stable, versioned contract — machine-parseable objective reality.
- Table and JSON derive from the same report object (no drift between views).

### 4.2 Negative Consequences
- The JSON schema is now a contract to maintain; breaking changes require a
  `report_version` bump (mitigation: golden-file tests + version field).
- Exit-code semantics must be documented and honored (mitigation: single source of truth
  in the CLI, tested).

### 4.3 Neutral Consequences
- The Rich table and JSON are two projections of one report model.

## 5. Implications

### 5.1 Architectural Implications
The drift report becomes a typed model with two renderers (table, JSON) and a versioned
serialization.

### 5.2 Technical Implications
A report serialization path; `--format`/`--exit-code` flags; golden-file tests.

### 5.3 Organizational Implications
CI pipelines and the agent consume JSON; humans keep the table.

### 5.4 Financial Implications
None.

### 5.5 Schedule Implications
None material; sequenced with ADR-013 (MCP) and ADR-015 (remediation) as one increment.

## 6. Related Documents
- **Supersedes**: None
- **Superseded By**: None
- **Related To**: ADR-008 (three-way classification), ADR-013 (MCP), ADR-015 (remediation)
- **Amends**: None
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
