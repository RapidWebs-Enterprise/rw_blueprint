# ARCHITECTURE DECISION RECORD
## Industry Standard Format for ADRs (2026)

## Document Identification
- **ADR ID**: 003
- **Title**: Python 3.11+ with Pydantic v2 / PyYAML / Jinja2 / Typer / Rich as the engine stack
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

- **Problem Statement**: Choose the language and libraries for the source-of-truth engine.
- **Drivers**: Must be LLM-friendly; must validate a YAML schema with referential integrity;
  must emit Mermaid/markdown/quadlet; must integrate with the 2026 Python toolchain (uv,
  ruff, mypy, pytest).
- **Assumptions**: The engine is a CLI + library, not a long-running service.
- **Constraints**: Finalize only after research (per stakeholder directive); remain open to
  change if research surfaces a better fit.

## 2. Decision

- **Decision Statement**: Implement in **Python 3.11+** using **Pydantic v2** (schema +
  validation), **PyYAML** (parse), **Jinja2** (templates), **Typer** (CLI), and **Rich**
  (output).
- **Considered Alternatives**:
  - **Alternative 1 — TypeScript (Marrow/Shumoku/TopoViewer stack)**:
    - **Pros**: Matches the ecosystem of interactive HTML renderers.
    - **Cons**: Those tools optimize for rendering, not agent-readable canonical models;
      diverges from our Python toolchain; no Pydantic-equivalent ergonomics for strict
      schema validation.
  - **Alternative 2 — Go**:
    - **Pros**: Single static binary; fast.
    - **Cons**: More ceremony for schema validation + templating; weaker LLM-ecosystem
      familiarity; slower iteration for a small tool.
  - **Alternative 3 — Rust**:
    - **Pros**: Performance, correctness.
    - **Cons**: Highest development cost; overkill for a batch CLI; serde schema ergonomics
      less direct than Pydantic for cross-field validation.
- **Decision Rationale**: Six independent projects in the research corpus (iacgen,
  semantic-diagrams, dockumentor, archspec, makejinja, diagrams-as-code) converged on this
  exact Python stack for this exact job. Pydantic v2 provides `extra="forbid"` +
  `model_validator` for the referential-integrity requirement with minimal code.
- **Implementation Approach**: `pyproject.toml` with the listed dependencies; `uv` for
  environment + lockfile; ruff/mypy/pytest for quality gates.

## 3. Status
Accepted.

## 4. Consequences

### 4.1 Positive Consequences
- Minimal, well-understood code for strict schema validation.
- Consistent with the 2026 Python toolchain already scaffolded.
- LLM-friendly (YAML + Python are the most common agent-native formats).

### 4.2 Negative Consequences
- Python startup overhead (negligible for a batch CLI).
- Not a single static binary (mitigated: `uv`/`pip` install).

### 4.3 Neutral Consequences
- The YAML schema remains language-agnostic regardless of engine language.

## 5. Implications

### 5.1 Architectural Implications
Engine language is an implementation detail; the schema is the contract.

### 5.2 Technical Implications
Pydantic v2 models are the validation layer; Jinja2 templates are the emission layer.

### 5.3 Organizational Implications
Contributors need Python 3.11+ familiarity.

### 5.4 Financial Implications
None.

### 5.5 Schedule Implications
None material.

## 6. Related Documents
- **Supersedes**: None
- **Superseded By**: None
- **Related To**: ADR-001 (YAML SoT), ADR-002 (in-house engine), ADR-004 (generator)
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