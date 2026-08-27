# ARCHITECTURE DECISION RECORD
## Industry Standard Format for ADRs (2026)

## Document Identification
- **ADR ID**: 001
- **Title**: YAML as the canonical source of truth (diagram-as-code) over IaC-as-source or full SoT platforms
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

- **Problem Statement**: The RWDN's "what is true" lives in multiple conflicting,
  hand-written markdown files that drift within 30–60 days (Itential research: 60% of
  documentation projects fail; accuracy degrades to 15–30% without automation). We need a
  single canonical, machine-readable model that humans, reproducibility tooling, and
  autonomous agents can all treat as objective reality.
- **Drivers**: Post-data-loss recovery; need for agent-readable "objective reality";
  desire to eliminate drift; no existing Terraform/state to build on.
- **Assumptions**: The topology is small-to-medium; consumers are humans + LLM agents, not
  a real-time control plane.
- **Constraints**: No Terraform currently deployed; must be LLM-parseable/diffable.

## 2. Decision

- **Decision Statement**: Adopt **diagram-as-code** — a structured YAML topology is the
  canonical source of truth, from which diagrams, docs, and IaC skeletons are *derived*.
- **Considered Alternatives**:
  - **Alternative 1 — IaC-as-source (Terraform/state → diagram)**:
    - **Pros**: Single source already drives deployment; drift detection built-in.
    - **Cons**: Requires adopting Terraform first (we don't have it); state files are not
      cleanly LLM-diffable; couples the model to a specific IaC tool.
  - **Alternative 2 — Full SoT platform (NetBox/Nautobot/Infrahub)**:
    - **Pros**: Battle-tested IPAM/DCIM; rich data model.
    - **Cons**: Heavy; 15–25% manual-entry overhead; overkill for a 1-host + few-container
      fleet; not natively agent-diffable as a flat YAML file.
- **Decision Rationale**: YAML is trivially parseable and generatable by LLMs, enabling the
  "ask an agent to add a VLAN → it produces the exact YAML diff" property (Prajwal Ravi,
  "Network Topology as Code"). It is tool-agnostic, so we are not locked into Terraform or
  a platform.
- **Implementation Approach**: Define a versioned `topology.yaml` schema; build a thin
  engine that validates it and emits derived artifacts.

## 3. Status
Accepted.

## 4. Consequences

### 4.1 Positive Consequences
- Single canonical model; derived artifacts cannot drift.
- LLM agents can read, diff, and propose changes as YAML diffs.
- Tool-agnostic — no lock-in to Terraform or a platform.

### 4.2 Negative Consequences
- We must build and maintain the schema + engine ourselves (mitigated: thin, ~a few
  hundred lines).
- No built-in live drift detection (deferred to a later phase).

### 4.3 Neutral Consequences
- YAML is the contract; any future rendering backend (Marrow/Shumoku) consumes it.

## 5. Implications

### 5.1 Architectural Implications
The YAML schema is the stable contract; the engine is one consumer. Rendering backends can
be swapped without touching the model.

### 5.2 Technical Implications
Requires a validation layer (Pydantic v2) enforcing referential integrity.

### 5.3 Organizational Implications
Contributors edit the YAML model, not the generated docs.

### 5.4 Financial Implications
None (open-source, self-hosted).

### 5.5 Schedule Implications
Adds a schema-design + engine-build phase before any RWDN stabilization can consume it.

## 6. Related Documents
- **Supersedes**: None
- **Superseded By**: None
- **Related To**: ADR-002 (in-house engine), ADR-003 (Python stack), ADR-004 (generator),
  ADR-005 (schema entities)
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