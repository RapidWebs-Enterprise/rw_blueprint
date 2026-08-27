# ARCHITECTURE DECISION RECORD
## Industry Standard Format for ADRs (2026)

## Document Identification
- **ADR ID**: 002
- **Title**: Build a thin in-house engine rather than adopt an external diagram-as-code tool
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

- **Problem Statement**: We need to turn a canonical YAML topology into diagrams, docs, and
  IaC skeletons. Existing tools (Marrow, Shumoku, TopoViewer, Archyl, diagrams-as-code)
  already do parts of this.
- **Drivers**: Need an agent-readable canonical file (not just a pretty diagram); need IaC
  skeleton emission (quadlet/Incus) that external renderers don't provide; want minimal
  maintenance surface.
- **Assumptions**: The engine's scope is bounded (validate + emit three artifact types).
- **Constraints**: Must not add a heavy dependency; must remain LLM-friendly.

## 2. Decision

- **Decision Statement**: Build a **thin in-house engine** (Python + Jinja2) around the
  canonical YAML model, rather than adopting Marrow/Shumoku/TopoViewer as the core.
- **Considered Alternatives**:
  - **Alternative 1 — Adopt Marrow**:
    - **Pros**: Mature topology YAML → interactive HTML; ships a Claude Code skill.
    - **Cons**: Output is interactive HTML (not agent-readable canonical model); no IaC
      skeleton emission; TypeScript stack diverges from our Python toolchain.
  - **Alternative 2 — Adopt TopoViewer**:
    - **Pros**: Clean model/presentation/telemetry separation.
    - **Cons**: React/MkDocs/Grafana stack; heavier; still no quadlet/Incus emission.
  - **Alternative 3 — Adopt Shumoku**:
    - **Pros**: 900+ vendor icons; live weathermap.
    - **Cons**: Heaviest; oriented to network-device inventory, not service topology.
- **Decision Rationale**: The canonical agent-readable YAML model is the *product*; external
  tools optimize for rendering, not for being an objective source of truth. A thin engine
  gives us exactly the three emissions we need with no lock-in.
- **Implementation Approach**: Pydantic v2 validation + Jinja2 templates → Mermaid /
  markdown / quadlet+Incus. Keep the YAML schema as the stable contract so Marrow/Shumoku
  can be bolted on later as a rendering backend.

## 3. Status
Accepted.

## 4. Consequences

### 4.1 Positive Consequences
- Full control over the canonical model and its emissions.
- IaC skeleton emission (quadlet/Incus) — not offered by external renderers.
- Minimal dependency surface; Python-consistent.

### 4.2 Negative Consequences
- We own the engine's correctness and maintenance (mitigated: small, well-tested scope).
- No interactive HTML out of the box (deferred; can bolt on later).

### 4.3 Neutral Consequences
- Mermaid output is the initial human-facing rendering; richer rendering is a later option.

## 5. Implications

### 5.1 Architectural Implications
Engine is a thin consumer of the schema; rendering backends are swappable.

### 5.2 Technical Implications
Requires Jinja2 templates for three output formats.

### 5.3 Organizational Implications
None beyond owning a small codebase.

### 5.4 Financial Implications
None.

### 5.5 Schedule Implications
Engine build is a bounded, near-term task.

## 6. Related Documents
- **Supersedes**: None
- **Superseded By**: None
- **Related To**: ADR-001 (YAML SoT), ADR-003 (Python stack), ADR-004 (generator)
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