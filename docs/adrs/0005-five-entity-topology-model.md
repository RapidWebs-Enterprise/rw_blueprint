# ARCHITECTURE DECISION RECORD
## Industry Standard Format for ADRs (2026)

## Document Identification
- **ADR ID**: 005
- **Title**: Five-entity topology model (zones, nodes, services, links, dependencies) with strict referential integrity
- **Status**: Accepted (amended 2026-08-27)
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

- **Problem Statement**: Define the canonical topology schema's entity model and its
  integrity rules.
- **Drivers**: Must be simultaneously human-readable, agent-queryable, and IaC-generatable;
  must eliminate drift by rejecting dangling references.
- **Assumptions**: Topology is small-to-medium; external entities (Cloudflare, internet)
  must be representable so links stay referential.
- **Constraints**: Stable unique `id` per entity; display names may drift.

## 2. Decision

- **Decision Statement**: Model the topology as **five entity types** — zones, nodes,
  services, links, and dependencies — with **strict referential integrity** enforced at
  parse time, and `id` as the stable key.
- **Considered Alternatives**:
  - **Alternative 1 — Node-centric only (no zones/services split)**:
    - **Pros**: Simpler.
    - **Cons**: Loses trust-boundary reasoning (zones) and workload/port modeling
      (services), both needed for firewall and IaC generation.
  - **Alternative 2 — Full NetBox-style data model (sites, racks, devices, IPAM, VLANs)**:
    - **Pros**: Comprehensive.
    - **Cons**: Overkill for a 1-host + few-container fleet; high entry overhead.
- **Decision Rationale**: Five entities capture exactly what is needed for diagrams
  (zones/nodes/links), docs (all), and IaC (services → quadlet, nodes → Incus profiles),
  without NetBox's weight. Referential integrity is the anti-drift property.
- **Implementation Approach**: Pydantic v2 models with `extra="forbid"` and a
  `model_validator` that checks every reference resolves and every `id` is unique.

## 3. Status
Accepted.

### 3.1 Amendment (2026-08-27)
The forward audit (see `docs/specs/audits/forward-audit-RWBP-2026-001.md`) found that
the initial implementation downgraded `Dependency` to a nested field on `Service`
rather than a first-class entity with its own `id`, contradicting the literal intent
of this ADR ("five entity types"). This amendment ratifies the correction:

- **`Dependency` is a first-class entity** with its own stable `id`, symmetric with
  `Link`. It carries `from`/`to` references (service ids) plus an optional `type`
  (e.g. `requires`, `depends_on`, `observes`).
- **`Link` remains the network-connectivity edge** (node-to-node, with `ports`),
  while **`Dependency` is the logical/operational edge** (service-to-service). The
  two are distinct concerns and must not be conflated.

This restores the five-entity model to its intended shape: zones, nodes, services,
links, dependencies.

## 4. Consequences

### 4.1 Positive Consequences
- Dangling references are impossible in a valid document.
- External entities are first-class (no special-casing links).
- Drives firewall (zones), IaC (services/nodes), and blast-radius (dependencies) reasoning.

### 4.2 Negative Consequences
- Schema is slightly more complex than a flat node list (mitigated: five small models).
- External entities must be explicitly declared as nodes.

### 4.3 Neutral Consequences
- `id` vs `name` distinction must be respected by all contributors.

## 5. Implications

### 5.1 Architectural Implications
The schema is the stable contract; all generators and the future agent consume it.

### 5.2 Technical Implications
Cross-field validation lives in a single `model_validator`.

### 5.3 Organizational Implications
Contributors must declare external entities and use stable ids.

### 5.4 Financial Implications
None.

### 5.5 Schedule Implications
None material.

## 6. Related Documents
- **Supersedes**: None
- **Superseded By**: None
- **Related To**: ADR-001, ADR-003
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