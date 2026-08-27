# ARCHITECTURE DECISION RECORD
## Industry Standard Format for ADRs (2026)

## Document Identification
- **ADR ID**: 006
- **Title**: Structured port model (`{port, protocol, public}`) over flat `list[int]`
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

- **Problem Statement**: The initial schema represented service ports as a flat
  `list[int]`. This is insufficient for correct IaC generation, which needs to know
  the protocol (tcp/udp) and whether a port is publicly exposed or internal-only.
- **Drivers**: Quadlet `PublishPort` and firewall rules both require protocol and
  exposure semantics; a bare integer cannot carry them.
- **Assumptions**: Most services are TCP; UDP is the exception, not the rule.
- **Constraints**: Must remain backward-compatible with the existing example topology
  where possible; must not over-engineer (no per-port ACLs yet).

## 2. Decision

- **Decision Statement**: Model each port as a structured object with three fields —
  `port` (int, required), `protocol` (enum `tcp`/`udp`, default `tcp`), and `public`
  (bool, default `false`). A service's `ports` field becomes a `list[Port]`.
- **Considered Alternatives**:
  - **Alternative 1 — Flat `list[int]`**:
    - **Pros**: Simplest; matches the original v0.1 spike.
    - **Cons**: Cannot express protocol or exposure; produces incorrect quadlet and
      firewall output for UDP or internal-only services.
  - **Alternative 2 — Full per-port ACL (source CIDRs, rate limits)**:
    - **Pros**: Complete firewall modeling.
    - **Cons**: Overkill for v0.1; belongs in a later firewall-specific entity.
- **Decision Rationale**: Three fields capture the minimum needed for correct IaC
  (quadlet `PublishPort` needs `public`; firewall needs `protocol`) without the
  weight of full ACL modeling. Defaults keep the common case terse.
- **Implementation Approach**: Pydantic `Port` model with `protocol: Literal["tcp","udp"]`
  defaulting to `tcp`, and `public: bool` defaulting to `false`.

## 3. Status
Accepted.

## 4. Consequences

### 4.1 Positive Consequences
- Quadlet generation can emit `PublishPort` only for `public: true` ports.
- Firewall generation can distinguish tcp/udp correctly.
- Internal-only services are correctly represented (no accidental exposure).

### 4.2 Negative Consequences
- Slightly more verbose YAML than a flat list (mitigated by defaults).

### 4.3 Neutral Consequences
- Contributors must specify `public: true` explicitly for exposed ports.

## 5. Implications

### 5.1 Architectural Implications
The `Port` model is a stable sub-schema consumed by all generators.

### 5.2 Technical Implications
Generators branch on `protocol` and `public`; the flat-list assumption is removed.

### 5.3 Organizational Implications
Contributors document exposure intent explicitly.

### 5.4 Financial Implications
None.

### 5.5 Schedule Implications
None material.

## 6. Related Documents
- **Supersedes**: None
- **Superseded By**: None
- **Related To**: ADR-005, ADR-003
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