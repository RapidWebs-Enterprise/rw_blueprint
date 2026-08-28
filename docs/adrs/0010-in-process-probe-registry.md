# ARCHITECTURE DECISION RECORD
## Industry Standard Format for ADRs (2026)

## Document Identification
- **ADR ID**: 010
- **Title**: In-process probe registry over a plugin framework
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

- **Problem Statement**: The probe layer needs a way to register and invoke multiple
  collectors (incus, podman, port, dns, tailscale). The question is whether to use a
  plugin framework (pluggy, stevedore, entry-points) or a simple in-process registry.
- **Drivers**: The research (Probe_Collector Plugin Architecture) found that for a small,
  fixed set of probes (~5), a plugin framework is over-engineering — it adds a discovery
  and loading mechanism that buys nothing at this scale. osquery's model (declarative
  observation, uniform output) is the valuable part, not its plugin system.
- **Assumptions**: The probe set is small and stable; probes are first-party (shipped with
  the tool), not third-party extensions.
- **Constraints**: Probes must be read-only by construction; the registry must be simple
  enough to audit for that property.

## 2. Decision

- **Decision Statement**: Implement probes as a simple **in-process registry** — a
  dictionary mapping probe name to a callable that emits a normalized fragment. No plugin
  framework, no dynamic discovery, no entry-points. Each probe is a first-party module.
- **Considered Alternatives**:
  - **Alternative 1 — Plugin framework (pluggy / stevedore / entry-points)**:
    - **Pros**: Third-party extensibility; hot-loading.
    - **Cons**: Adds a discovery/loading mechanism and indirection; harder to audit the
      read-only property; overkill for 5 first-party probes.
  - **Alternative 2 — Standalone scripts (no registry)**:
    - **Pros**: Simplest possible.
    - **Cons**: No uniform invocation or output contract; the reconciler would need to know
      each probe's idiosyncrasies.
- **Decision Rationale**: A registry gives the uniform contract (the reconciler's need)
  without the weight of a plugin framework (which buys nothing at this scale).
- **Implementation Approach**: A `probes` module with a `PROBES: dict[str, Callable]`
  registry; each probe is a function returning a `live_state` fragment. A plugin framework
  can be introduced later if third-party probes ever become a requirement.

## 3. Status
Accepted.

## 4. Consequences

### 4.1 Positive Consequences
- Simple, auditable, read-only-by-construction.
- Uniform invocation and output contract.
- No dependency on a plugin framework.

### 4.2 Negative Consequences
- No third-party probe extensibility. Mitigation: the registry is a stable seam; a plugin
  framework can be layered on later without changing the probe contract.

### 4.3 Neutral Consequences
- Probes are first-party modules shipped with the tool.

## 5. Implications

### 5.1 Architectural Implications
The registry is the stable seam between probes and the reconciler.

### 5.2 Technical Implications
A `PROBES` dict; each probe is a pure-ish function (read-only, emits a fragment).

### 5.3 Organizational Implications
None.

### 5.4 Financial Implications
None.

### 5.5 Schedule Implications
None material.

## 6. Related Documents
- **Supersedes**: None
- **Superseded By**: None
- **Related To**: ADR-009 (pull-first), ADR-012 (osquery model)
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