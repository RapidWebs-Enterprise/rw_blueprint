# REVERSE AUDIT — RWBP-2026-001 (rw_blueprint)

- **Audit type**: Reverse (gaps, edge cases, adversarial review)
- **Date**: 2026-08-27
- **Auditor**: Network Systems Specialist
- **Method**: Inline (project <10 source files)
- **Scope**: Find what the SPEC/ADRs missed, plus security/edge-case issues in the
  implementation that the forward audit (which only traces requirement→code) does not catch.

---

## 1. Contract gaps (SPEC/ADR omissions)

### G-1 — `schema_version` is not enforced
- **Issue**: `Topology.schema_version` defaults to `"0.1"` (`schema.py:97`) and is never
  validated against the actual `SCHEMA_VERSION` constant (`schema.py:28`). A document
  declaring `schema_version: "9.9"` would parse silently.
- **Risk**: Version drift — the exact class of problem this project exists to eliminate.
- **Recommendation**: Reject documents whose `schema_version` does not match the supported
  version, with a clear "unsupported schema version" error.

### G-2 — No round-trip test (SPEC §5.2 / §8.3 requires it)
- **Issue**: SPEC §5.2 "Data Integrity" and §8.3 "Non-Functional Test Requirements" both
  require a "round-trip losslessness test (parse → dump → parse)". No such test exists.
- **Evidence**: `tests/test_schema.py` has `test_link_from_alias_round_trips` (`:140-144`)
  which checks *one field's* alias, but no full `model_dump` → `model_validate` round-trip.
- **Recommendation**: Add a full round-trip test.

### G-3 — No "no-secret" assertion (SPEC §8.3 requires it)
- **Issue**: SPEC §8.3 requires a "no-secret assertion on generated output." No test
  asserts that generated artifacts are free of secrets.
- **Note**: The schema has no secret field, so this is currently vacuously true — but the
  requirement is untested and unenforced. If a future field (e.g., `api_key`) is added,
  nothing would stop it leaking into generated output.
- **Recommendation**: Add a test asserting generated output contains no secret-like
  patterns, and document the "secrets by reference only" rule in the schema.

### G-4 — `kind` is an unconstrained `str`
- **Issue**: `Service.kind` is `str` (`schema.py:74`), not a `Literal`. The SPEC/ADR imply
  a bounded set (e.g., `database`, `application`, `proxy`). An unconstrained string means
  typos like `kind: databse` pass validation and silently produce wrong IaC.
- **Recommendation**: Constrain `kind` to a `Literal` enum (or at minimum document the
  allowed values).

### G-5 — `ports` flat `list[int]` loses protocol/public mapping
- **Issue**: This is the SPEC §9 open issue that was resolved unilaterally (flat list).
  The quadlet template emits `PublishPort={{ p }}:{{ p }}` (`quadlet.container.j2:12`),
  which assumes host port == container port and protocol == tcp. There is no way to express
  a host-port≠container-port mapping or a UDP port.
- **Risk**: Incorrect IaC for any service with non-1:1 port mapping (common in practice).
- **Recommendation**: Promote to a structured port object in v2 (see synthesis).

### G-6 — No `image` field on `Service`
- **Issue**: The quadlet template emits `Image=REPLACE_ME` (`quadlet.container.j2:11`) —
  a literal placeholder. The schema has no field for the container image, so the generated
  quadlet is **not deployable as-is**.
- **Risk**: The "IaC skeleton" is a stub, not a usable artifact. This is arguably correct
  for a "skeleton," but the SPEC never states that images are out of scope.
- **Recommendation**: Either add an `image` field (and emit it), or explicitly document in
  the SPEC that images are intentionally placeholders.

### G-7 — Incus profile is a near-empty stub
- **Issue**: `incus.profile.j2` emits `config: {}` and `devices: {}` (`incus.profile.j2:6-7`).
  The profile carries no actual configuration (no `limits.cpu`, `limits.memory`, no NIC
  device). It is a name-only placeholder.
- **Risk**: Same as G-6 — the "IaC skeleton" is not meaningful yet.
- **Recommendation**: Document the intended profile contents, or add fields (cpu/memory/nic)
  to the `Node` model.

### G-8 — `Link` has no `direction` semantics documented
- **Issue**: This is the other SPEC §9 open issue, resolved unilaterally as "directed,
  implicit in from/to." The Mermaid template renders `A --> B` (`topology.mmd.j2:12`),
  which is correct for directed links, but the SPEC/ADR never ratified this. A bidirectional
  link (e.g., a mesh peer) cannot be expressed.
- **Recommendation**: Ratify the directed-link decision in v2, and note that bidirectional
  links require two `Link` entries (or add a `bidirectional: bool` field).

---

## 2. Security / adversarial findings

### S-1 — `load_topology` reads arbitrary paths (no path validation)
- **Evidence**: `generator.py:33` `Path(path).read_text()` with no validation.
- **Risk**: Low (local CLI, trusted operator), but the CLI accepts any path. Not a
  traversal vulnerability in the MCP sense (no remote caller), but worth noting for the
  future agent-integration surface (ADR-001's "agent reads the model").
- **Recommendation**: Defer; flag for the P5 agent phase where the model becomes an
  agent-facing input.

### S-2 — `autoescape=False` is justified but fragile
- **Evidence**: `generator.py:45` `autoescape=False  # noqa: S701`.
- **Assessment**: Correct — output is Mermaid/markdown/quadlet text, not HTML. The `noqa`
  is justified. No action needed, but the justification comment should remain.

### S-3 — No size/DoS guard on input
- **Evidence**: `load_topology` reads the entire file with no size limit.
- **Risk**: Low for a CLI, but a maliciously large YAML could exhaust memory. Relevant for
  the future agent phase.
- **Recommendation**: Defer; note for P5.

---

## 3. Test-coverage gaps

| Gap | Detail |
|-----|--------|
| T-1 | Duplicate zone/service/link ids are implemented but not individually tested (only node tested) |
| T-2 | No round-trip test (G-2) |
| T-3 | No no-secret test (G-3) |
| T-4 | No test for `schema_version` mismatch (G-1) |
| T-5 | No test for empty-file / non-YAML input to `load_topology` (the `ValueError`/`YAMLError` branches) |
| T-6 | No test for the `validate`/`generate` CLI exit codes (REQ-005/006 acceptance criteria) |

---

## 4. Summary of findings

| ID | Severity | Finding |
|----|----------|---------|
| G-1 | High | `schema_version` not enforced |
| G-2 | Medium | No round-trip test (SPEC requires) |
| G-3 | Medium | No no-secret assertion (SPEC requires) |
| G-4 | Medium | `kind` unconstrained string |
| G-5 | Medium | `ports` flat list loses protocol/public mapping |
| G-6 | Medium | Quadlet `Image=REPLACE_ME` placeholder (no image field) |
| G-7 | Low | Incus profile is a name-only stub |
| G-8 | Low | Link direction not ratified |
| S-1 | Low | No path validation (defer to P5) |
| S-3 | Low | No input size guard (defer to P5) |

**Primary finding (reverse)**: The SPEC's own non-functional requirements (§5.2 round-trip,
§8.3 no-secret) are **not implemented or tested**, and the IaC skeletons are placeholders
(`Image=REPLACE_ME`, empty Incus profile) whose scope is undocumented. Combined with the
forward audit's "five entities vs four" finding, these form the v2 synthesis backlog.