# ARCHITECTURE DECISION RECORD
## Industry Standard Format for ADRs (2026)

## Document Identification
- **ADR ID**: 016
- **Title**: Schema migration via a chained handler registry
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

- **Problem Statement**: The schema enforces `schema_version` (ADR-005/006) but offers no
  upgrade path. The schema already went 0.1→0.2 (flat `ports` → structured `Port`), which
  stranded any pre-0.2 `topology.yaml`. Enforce-and-reject is half the story; without a
  migration path, every breaking schema change orphans old models.
- **Drivers**: SUEWS is the reference implementation — a chained migration-handler
  registry, a `migrate` command with `--dry-run` and `--target-version`, `.bak` safety,
  and the rule that **additive changes do not bump the schema; breaking changes bump +
  register a handler**. versionedconfig (Go) chains `UpgradeTo` functions oldest→newest;
  Marrow ships `import`/`--target-version` for legacy YAML; Digitorn uses an alias pass so
  legacy files keep parsing.
- **Assumptions**: Schema changes are infrequent; breaking changes are deliberate and
  must carry a migration.
- **Constraints**: Must preserve user values through renames; must be reversible
  (dry-run); must not silently drop fields without logging them.

## 2. Decision

- **Decision Statement**: Add a **chained migration-handler registry** and a `migrate`
  CLI command. Compatibility is defined as: a document's `schema_version` is compatible
  with the current version iff it equals the current version **or** a registered handler
  chain connects them. **Additive, backward-compatible changes do not bump
  `schema_version`; breaking changes (rename, remove, type change, restructure) bump it
  and register a handler.** `migrate` supports `--dry-run` and `--target-version`, writes
  a `.bak`, and logs dropped/renamed fields.
- **Considered Alternatives**:
  - **Alternative 1 — Reject-and-require-manual-rewrite (status quo)**:
    - **Pros**: Simplest; no migration code to maintain.
    - **Cons**: Strands old models; users hand-edit, which is exactly the drift this
      project exists to kill.
  - **Alternative 2 — Auto-detect shape (Digitorn alias pass)**:
    - **Pros**: Legacy files "just work" with no migration command.
    - **Cons**: Implicit reshaping is harder to reason about and audit; a hidden
      alias pass can mask drift.
- **Decision Rationale**: Chained handlers give a deterministic, auditable, reversible
  upgrade path while keeping the strict enforcement that is the anti-drift property. The
  additive-vs-breaking rule minimizes churn (most changes don't bump).
- **Implementation Approach**: A `_MIGRATIONS` dict keyed by `(from_version, to_version)`
  (mirroring SUEWS `_HANDLERS`); a `migrate` subcommand that walks the chain
  oldest→newest; a `--dry-run` that prints the rename/drop delta without writing.

## 3. Status

Proposed — awaiting review.

## 4. Consequences

### 4.1 Positive Consequences
- Old `topology.yaml` files upgrade safely and reversibly; user values survive renames.
- The additive-vs-breaking rule keeps `schema_version` stable across most releases.
- Dry-run + `.bak` make migration reviewable and reversible.

### 4.2 Negative Consequences
- Migration handlers are a new code + test surface to maintain (mitigation: handlers are
  small, pure, and golden-tested).
- A missed handler means a version is not migratable (mitigation: compatibility is
  *derived* from the registry, so a missing handler fails loudly, per SUEWS).

### 4.3 Neutral Consequences
- The `schema_version` field semantics become explicit (structure-only, not model version).

## 5. Implications

### 5.1 Architectural Implications
Schema evolution becomes a first-class, versioned, migratable concern.

### 5.2 Technical Implications
A migration registry, a `migrate` subcommand, and migration tests/golden files.

### 5.3 Organizational Implications
Breaking schema changes require a migration handler in the same change; documented in
CONTRIBUTING.md.

### 5.4 Financial Implications
None.

### 5.5 Schedule Implications
None material; additive.

## 6. Related Documents
- **Supersedes**: None
- **Superseded By**: None
- **Related To**: ADR-005 (five-entity model), ADR-006 (structured ports)
- **Amends**: ADR-005/006 (adds the migration path to the existing `schema_version`
  enforcement; does not change the entity model)
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
