# ARCHITECTURE DECISION RECORD
## Industry Standard Format for ADRs (2026)

## Document Identification
- **ADR ID**: 013
- **Title**: MCP server as the agent integration surface
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

- **Problem Statement**: `rw_blueprint`'s stated purpose is to give agents "something
  real and physical to use objectively", yet it exposes no agent-consumable interface —
  an agent can only shell out to the CLI and parse human-oriented output. The tool is
  a library, not a capability surface.
- **Drivers**: The gap-analysis research (Ecosystem_Gap_Analysis) found that every
  comparable project ships an MCP server (iso-topology: 7 tools; drawio-mcp-server: 20;
  awslabs/diagram-as-code: `awsdac-mcp-server`; kdrift: 4). FastMCP is the de-facto
  standard (per Prefect, some version powers ~70% of MCP servers across languages), and
  its `@mcp.tool()` decorator auto-generates JSON Schema from existing type hints. The
  four existing verbs (`validate`, `generate`, `probe`, `reconcile`) map 1:1 to MCP tools.
- **Assumptions**: The tool's consumers are human operators *and* (future) agents, both
  of which benefit from a schema-typed, approval-gated capability surface.
- **Constraints**: ADR-011 (apply-is-gated) must not be weakened; the MCP surface must
  preserve the emit-untrusted/apply-gated boundary.

## 2. Decision

- **Decision Statement**: Expose the four verbs as **MCP tools** via FastMCP (the
  official `mcp` Python SDK, pinned `mcp>=1.27,<2`), and expose the declared model and
  the drift report as **read-only MCP resources**. The CLI remains the primary human
  interface; the MCP server is a thin adapter over the same functions — no logic forks.
- **Considered Alternatives**:
  - **Alternative 1 — CLI-only (status quo)**:
    - **Pros**: No new dependency; simplest.
    - **Cons**: Agents must shell out and parse text output; no schema, no approval
      gate, no portability across agent hosts.
  - **Alternative 2 — REST API**:
    - **Pros**: Language-agnostic; cacheable.
    - **Cons**: Heavier (server, auth, deployment); does not integrate natively with
      agent hosts; reinvents what MCP already standardizes.
  - **Alternative 3 — LangGraph-native integration**:
    - **Pros**: Deep integration with one framework.
    - **Cons**: Non-portable; ties the tool to a single orchestration framework.
- **Decision Rationale**: MCP is the open, host-agnostic standard; it auto-generates the
  schema from the code that already exists, and its "tools require user approval before
  execution" default *reinforces* ADR-011 rather than weakening it. The MCP surface is
  the real answer to "agents have objective reality to reason against".
- **Implementation Approach**: Add an `mcp` module with `@mcp.tool()` wrappers over the
  existing `validate`/`generate`/`probe`/`reconcile` functions and `@mcp.resource()`
  readers for `topology.yaml` and the drift report. Register a `rw-blueprint-mcp`
  console entry point. Keep the CLI and MCP path pointing at the same pure functions.

## 3. Status

Accepted.

## 4. Consequences

### 4.1 Positive Consequences
- Agents consume the tool as a typed capability surface, not via shell-out text parsing.
- JSON Schema is auto-generated from existing Pydantic/type-hint signatures.
- Portable across any MCP host (Claude, Cursor, Goose, in-house harness).
- MCP's approval-on-invocation default hardens the ADR-011 boundary.

### 4.2 Negative Consequences
- New runtime dependency (`mcp`); must pin `<2` until the breaking v2 rename lands.
- Each tool becomes an attack surface (it executes code); mitigation: read-only-by-default
  verbs only, no write path, approval required per invocation.
- Two interfaces (CLI + MCP) to keep in sync; mitigation: both delegate to the same
  pure functions, asserted by test.

### 4.3 Neutral Consequences
- The MCP server is a facade, not a new capability — it exposes what already exists.

## 5. Implications

### 5.1 Architectural Implications
Introduces a third consumer surface (CLI, library, MCP) over the same core functions.

### 5.2 Technical Implications
Adds `mcp` to dependencies; a new `mcp` module; an entry point; schema auto-generation.

### 5.3 Organizational Implications
Enables the P5 agent to consume the tool natively rather than via subprocess.

### 5.4 Financial Implications
None (local stdio transport; no hosted gateway required).

### 5.5 Schedule Implications
Small, additive increment; does not block other work.

## 6. Related Documents
- **Supersedes**: None
- **Superseded By**: None
- **Related To**: ADR-011 (apply-is-gated), ADR-002 (thin engine)
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
