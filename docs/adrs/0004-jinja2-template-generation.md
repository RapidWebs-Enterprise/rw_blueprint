# ARCHITECTURE DECISION RECORD
## Industry Standard Format for ADRs (2026)

## Document Identification
- **ADR ID**: 004
- **Title**: Jinja2 template-based generation over programmatic code-gen for derived artifacts
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

- **Problem Statement**: Choose how the engine emits Mermaid diagrams, markdown docs, and
  quadlet/Incus IaC skeletons from the validated model.
- **Drivers**: Determinism; maintainability; separation of model (data) from presentation
  (templates); ease of adding new output formats.
- **Assumptions**: Three output formats initially, with more possible later.
- **Constraints**: Output must be deterministic and byte-identical across runs.

## 2. Decision

- **Decision Statement**: Use **Jinja2 templates** for each output format, driven by the
  validated Pydantic model, rather than hand-written string-building code.
- **Considered Alternatives**:
  - **Alternative 1 — Programmatic code-gen (f-strings / string builders)**:
    - **Pros**: No template engine dependency; full control.
    - **Cons**: Presentation logic entangled with model logic; harder to add formats;
      harder to review output shape; more error-prone.
  - **Alternative 2 — Code-generation libraries (e.g., emitting Python that emits)**:
    - **Pros**: Type-safe output.
    - **Cons**: Overkill for text artifacts; adds indirection.
- **Decision Rationale**: Jinja2 cleanly separates the model (data) from presentation
  (templates), making each output format a reviewable template file. It is deterministic
  given deterministic input, satisfying REQ-007.
- **Implementation Approach**: One template per format under `src/rw_blueprint/templates/`;
  a generator module renders each against the model.

## 3. Status
Accepted.

## 4. Consequences

### 4.1 Positive Consequences
- Clean model/presentation separation.
- Adding a format = adding a template.
- Deterministic, reviewable output.

### 4.2 Negative Consequences
- Template syntax is a small learning curve (mitigated: Jinja2 is ubiquitous).
- Templates are not type-checked by mypy (mitigated: render tests assert output shape).

### 4.3 Neutral Consequences
- Templates live alongside the schema as first-class source.

## 5. Implications

### 5.1 Architectural Implications
Generator is a thin renderer over the model; no logic in templates beyond presentation.

### 5.2 Technical Implications
Jinja2 is already a declared dependency.

### 5.3 Organizational Implications
Contributors edit templates to change output shape, not Python code.

### 5.4 Financial Implications
None.

### 5.5 Schedule Implications
None material.

## 6. Related Documents
- **Supersedes**: None
- **Superseded By**: None
- **Related To**: ADR-001, ADR-002, ADR-003
- **Amends**: None
- **Referenced By**: RWBP-2026-001 SPEC

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