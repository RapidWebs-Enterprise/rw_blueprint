# ARCHITECTURE DECISION RECORD
## Industry Standard Format for ADRs (2026)

## Document Identification
- **ADR ID**: 007
- **Title**: Live-state schema as a projection of the topology schema (not a parallel schema)
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

- **Problem Statement**: The reconcile layer needs to compare declared state
  (`topology.yaml`) against observed state. If observed state uses a *different* schema
  than declared state, the diff becomes a mapping problem between two vocabularies — a
  source of bugs and a barrier to agent reasoning.
- **Drivers**: The agent must reason against *one* vocabulary. The research (Live_State
  Schema Projection Contract) found that a projection — a schema whose entity shapes are a
  subset of the declared schema's shapes — makes the diff mechanical and the vocabulary
  shared.
- **Assumptions**: Not all declared entities are observable at runtime (zones and
  dependencies are design/logical concepts, not runtime facts).
- **Constraints**: Must reuse the existing Pydantic v2 topology schema (RWBP-2026-001);
  must not introduce a second, divergent model.

## 2. Decision

- **Decision Statement**: Model the live-state schema as a **projection** of the topology
  schema. Observable entities (`node`, `service`, `link`) reuse the same `id` vocabulary and
  field shapes as the declared model; non-observable entities (`zone`, `dependency`) are
  absent from live state. The reconciler diffs declared vs. observed using shared `id`
  keys.
- **Considered Alternatives**:
  - **Alternative 1 — Parallel schema (independent live-state model)**:
    - **Pros**: Full freedom to shape live state to whatever probes emit.
    - **Cons**: Two vocabularies; the diff becomes a mapping problem; agent must learn two
      models; drift between the two schemas themselves.
  - **Alternative 2 — Full topology schema for live state (no projection)**:
    - **Pros**: Symmetric, no subset logic.
    - **Cons**: Forces probes to emit non-observable entities (zones/dependencies) that
      they cannot actually observe, producing fabricated data.
- **Decision Rationale**: A projection gives the shared vocabulary (mechanical diff,
  single agent model) while honestly representing that only some entities are observable.
- **Implementation Approach**: A `live_state` module whose `Node`/`Service`/`Link` models
  are **thin Pydantic subclasses** of the topology models with non-observable fields made
  optional. A factory function `to_live_state(topology: Topology) -> LiveState` converts
  declared → live-state shape. `id` semantics are identical to the declared model.

## 3. Status
Accepted.

## 4. Consequences

### 4.1 Positive Consequences
- Diff is mechanical: match on `id`, compare shared fields.
- Agent reasons against one vocabulary.
- No schema-to-schema drift.

### 4.2 Negative Consequences
- Live state cannot express runtime-only facts that have no declared counterpart (e.g. a
  container's PID). Mitigation: such facts are captured as `extra` findings, not as schema
  fields.

### 4.3 Neutral Consequences
- Probes must map their raw output into the projection shape.

## 5. Implications

### 5.1 Architectural Implications
The projection is a stable contract between probes, reconciler, and agent.

### 5.2 Technical Implications
Reuse of the topology schema's Pydantic models; a small `live_state` wrapper with thin
subclasses.

### 5.3 Organizational Implications
Contributors learn one entity vocabulary.

### 5.4 Financial Implications
None.

### 5.5 Schedule Implications
None material.

## 6. Related Documents
- **Supersedes**: None
- **Superseded By**: None
- **Related To**: ADR-005 (five-entity model), ADR-008 (drift classification)
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