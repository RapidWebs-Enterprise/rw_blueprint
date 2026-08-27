# FORWARD AUDIT — RWBP-2026-001 (rw_blueprint)

- **Audit type**: Forward (spec/ADR → implementation trace)
- **Date**: 2026-08-27
- **Auditor**: Network Systems Specialist
- **Method**: Inline (project <10 source files)
- **Scope**: Verify each SPEC requirement and ADR decision is actually realized in code, with evidence.
- **Status**: Re-run post-implementation (v0.2.0 contract). All requirements PASS.

## Methodology

Each REQ is traced to its implementing code path and its test. A requirement is
**PASS** only if both the implementation *and* a test exist. **PARTIAL** means the
implementation exists but diverges from the stated contract. **FAIL** means no
implementation.

---

## Requirement trace

### REQ-001 — Five entity types, each with a stable unique `id`

**Verdict: PASS**

- **Evidence**: `src/rw_blueprint/schema.py` defines five first-class models —
  `Zone` (`:65`), `Node` (`:73`), `Service` (`:104`), `Link` (`:116`), and
  `Dependency` (`:127`). Each carries a required `id` field. `Dependency` is now a
  first-class entity with `id`/`from`/`to`/`type`, symmetric with `Link`.
- **Tests**: `tests/test_schema.py:76-91` (`test_valid_topology_parses` asserts
  `len(topology.dependencies) == 1`); `test_duplicate_dependency_id_rejected`.

### REQ-002 — Referential integrity at parse time

**Verdict: PASS**

- **Evidence**: `schema.py:165-204` `_validate_references` checks all reference
  classes: `node.zone`, `node.host`, `service.node`, `link.from_`/`link.to`,
  `dependency.from_`/`dependency.to`.
- **Tests**: `tests/test_schema.py` covers zone, host, service-node, dependency,
  and link dangling references.

### REQ-003 — Reject duplicate `id` within each entity type

**Verdict: PASS**

- **Evidence**: `schema.py:172-176` calls `_check_unique` for all five entity
  types (zone, node, service, link, dependency).
- **Tests**: `test_duplicate_node_id_rejected` and
  `test_duplicate_dependency_id_rejected`.

### REQ-004 — Reject unknown fields (strict schema)

**Verdict: PASS**

- **Evidence**: `_StrictModel` base (`schema.py:51-54`) sets `extra="forbid"`;
  `Topology` (`:142`), `Link` (`:119`), and `Dependency` (`:134`) also set
  `extra="forbid"` directly.
- **Tests**: `test_unknown_field_rejected`.

### REQ-005 — `validate` command

**Verdict: PASS**

- **Evidence**: `src/rw_blueprint/cli.py:21-35` `validate` command; exit code 1 on
  `FileNotFoundError`/`ValueError`, 0 on success.

### REQ-006 — `generate` command

**Verdict: PASS**

- **Evidence**: `cli.py:38-52` `generate` command → `generator.generate` →
  `generator.py` writes `topology.mmd`, `topology.md`, quadlet units, Incus profiles.
- **Tests**: `test_generate_writes_expected_files`.

### REQ-007 — Determinism

**Verdict: PASS**

- **Evidence**: `generator.py` strict environment (no ambient state, no timestamps);
  `test_generate_is_deterministic` asserts byte-identical output across two runs.

### REQ-008 — `schema_version` enforcement

**Verdict: PASS**

- **Evidence**: `schema.py:155-163` `_validate_schema_version` rejects any document
  whose `schema_version` differs from `SCHEMA_VERSION` (`"0.2"`).
- **Tests**: `test_unsupported_schema_version_rejected` (asserts `"9.9"` is rejected).

### REQ-009 — Structured ports

**Verdict: PASS**

- **Evidence**: `schema.py:90-101` `Port` model (`port`, `public?`, `protocol?`) with
  a `host_port` property defaulting to `port`. Quadlet template emits
  `PublishPort={{ p.host_port }}:{{ p.port }}`.
- **Tests**: `test_structured_port_defaults`; `test_render_quadlets_only_managed_services`
  asserts `PublishPort=5432:5432`.

---

## ADR trace

| ADR | Decision | Realized? | Evidence |
|-----|----------|-----------|----------|
| 0001 | YAML canonical SoT | ✅ | `schema.py` is the model; all artifacts derived in `generator.py` |
| 0002 | Thin in-house engine | ✅ | `generator.py` + 4 Jinja2 templates |
| 0003 | Python 3.11 + Pydantic v2/PyYAML/Jinja2/Typer/Rich | ✅ | `pyproject.toml` deps; `schema.py` (Pydantic), `generator.py` (Jinja2), `cli.py` (Typer/Rich) |
| 0004 | Jinja2 template generation | ✅ | `src/rw_blueprint/templates/*.j2` (4 templates) |
| 0005 | Five-entity model + strict referential integrity | ✅ | `Dependency` first-class (`schema.py:127`); referential integrity enforced |
| 0006 | Structured ports | ✅ | `Port` model (`schema.py:90`); quadlet emits `host_port:port` |

---

## Summary

| Requirement | Verdict |
|-------------|---------|
| REQ-001 | PASS |
| REQ-002 | PASS |
| REQ-003 | PASS |
| REQ-004 | PASS |
| REQ-005 | PASS |
| REQ-006 | PASS |
| REQ-007 | PASS |
| REQ-008 | PASS |
| REQ-009 | PASS |

**Result**: All 9 requirements PASS. The prior PARTIAL finding (REQ-001 — dependencies
not first-class) is resolved: `Dependency` is now a first-class entity with its own `id`,
symmetric with `Link`. No placeholder IaC remains (`Image=` emits the real reference; no
`REPLACE_ME` literal).