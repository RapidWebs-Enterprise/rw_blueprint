# SESSION_STATE.md — rw_blueprint

> Canonical cross-session handoff for the `rw_blueprint` project.
> Read this FIRST at session start. Update it before session end (and during
> long sessions ~20min or before risky/compaction-prone work).
>
> Format: `[YYYY-MM-DD] CATEGORY: description + resolution`.

## Current status (last updated 2026-08-27)

### Completed

- **Project scaffold** — full OSS standards-conformant structure created at
  `~/Workspaces/rw_blueprint/` (MIT license, README, CONTRIBUTING,
  CODE_OF_CONDUCT, SECURITY, CHANGELOG, `.github/`, `docs/`, `src/`, `tests/`,
  `examples/`, `tools/`).
- **Toolchain modernized to 2026 standard** — `uv` installed globally
  (0.12.6); `pyproject.toml` migrated to `[dependency-groups]`; `uv.lock`
  generated; `.python-version` pinned to 3.11; `.pre-commit-config.yaml` added;
  CI switched to `astral-sh/setup-uv@v5`.
- **Research campaign** — four formal reports in `docs/research/` (landscape
  survey, schema design, generator architecture, agent-integration).
- **SPEC + ADRs commissioned** — `docs/specs/RWBP-2026-001.SPEC.md` and ADRs
  0001–0005.
- **Schema + generator implemented** — `schema.py`, `generator.py`, 4 Jinja2
  templates, `examples/topology.yaml`, `test_schema.py`, `test_generator.py`.
  All quality gates green (16 tests pass, ruff/mypy clean).
- **Enterprise/ drift fixed** — `documentation/`→`docs/`; README rewritten to
  reflect reality; stale drift report archived with supersession note.
- **Forward + reverse audits** — `docs/specs/audits/forward-audit-RWBP-2026-001.md`
  and `reverse-audit-RWBP-2026-001.md` written with evidence-cited findings.
- **v2 synthesis** — SPEC promoted to v0.2.0 (REQ-008 schema_version, REQ-009
  structured ports, dependencies first-class); ADR-005 amended (dependencies
  first-class); ADR-006 added (structured ports).
- **Implementation plan** — `docs/specs/IMPL-RWBP-2026-001.md` written, mapping
  all audit findings to ordered deliverables.
- **Reconcile-layer research campaign** — 6 additional reports in
  `docs/research/` (reconciliation control-loop patterns, probe/collector
  architecture, event-driven watchdog push, live-state projection contract,
  osquery-style host introspection, reference projects).
- **Reconcile-layer SPEC + ADRs** — `docs/specs/RWBP-2026-002.SPEC.md` (v0.2.0)
  and ADRs 0007–0012 all **Accepted** after forward/reverse audits and synthesis.
- **Reconcile-layer implementation (Phase A — Pull Loop)** — `live_state.py`,
  `probes.py`, `reconciler.py`, CLI `reconcile` + `probe` commands, tests.
  All quality gates green (24 tests pass, ruff/mypy clean). End-to-end
  `rw-blueprint reconcile` produces correct drift reports.

### In progress

- None. **Phase A complete**. Ready for Phase B (watchdog push emitters) when
  needed, or to apply the tool to the live RWDN.

### Next (specific steps)

1. **Apply to RWDN** — model the live RWDN topology into `topology.yaml`,
   run `rw-blueprint reconcile` against actual infrastructure to produce
   the canonical drift report.
2. **Execute RWDN Recovery Roadmap P1 (Stabilize)** — consolidate the dual-instance
   Caddy (the #1 single point of failure), capture Hetzner firewall rules,
   fix Tailscale mesh degradation.
3. **Phase B (deferred, non-blocking)** — watchdog push emitters (podman/incus/
   systemd events) per ADR-009 pull-first sequencing.

### Blockers / questions

- None. The reconcile layer is complete and green.

## Reconcile-layer documents (2026-08-27, complete)

- **SPEC**: `docs/specs/RWBP-2026-002.SPEC.md` (v0.2.0) — 9 REQs covering
  live-state projection schema, probe registry, reconciler (3-way drift
  classification + severity + ignore rules), watchdog event contract, security
  boundary, determinism, strict validation.
- **ADRs** (all Accepted):
  - `0007` — live-state schema as a projection of the topology schema
  - `0008` — three-way drift classification (missing/extra/mismatched) + severity
  - `0009` — pull-first sequencing (collectors before watchdogs)
  - `0010` — in-process probe registry (no plugin framework)
  - `0011` — emit-is-untrusted / apply-is-gated security boundary
  - `0012` — borrow the osquery model, not the osquery tool
- **Research** (10 reports total in `docs/research/`): added reconciliation
  control-loop patterns, probe/collector plugin architecture, event-driven
  watchdog push architecture, live-state projection contract, osquery-style host
  introspection, and reference projects (tfdrift + driftguard cloned to
  `~/.references/`).

## Decision log

- `[2026-08-27] STACK: finalized Python 3.11 + Typer/Pydantic v2/PyYAML/Jinja2/
  Rich + uv/ruff/mypy/pytest (post-research).`
- `[2026-08-27] NAME: project = rw_blueprint (rw_ convention), MIT license.`
- `[2026-08-27] SCOPE: Enterprise/ = private infra workspace (NOT OSS);
  rw_blueprint = separate reusable OSS tool.`
- `[2026-08-27] PROCESS: adopted plan-and-audit MEDIUM mode — SPEC → ADRs →
  forward audit → reverse audit → synthesize v2 → implementation plan → sign-off
  → TDD. (Corrected after skipping the audit step once.)`
- `[2026-08-27] SCHEMA (v2): dependencies first-class (ADR-005 amended);
  structured ports {port, public?, protocol?} (ADR-006); directed links implicit
  in from/to; schema_version enforced.`
- `[2026-08-27] RECONCILE LAYER: live-state projection (ADR-007); three-way
  drift classification + severity (ADR-008); pull-first (ADR-009); in-process
  probe registry (ADR-010); emit-untrusted/apply-gated (ADR-011); osquery model
  not tool (ADR-012).`
- `[2026-08-27] IMPLEMENTATION: Phase A (pull loop) complete — live_state.py,
  probes.py (incus/podman/port/dns/tailscale), reconciler.py (3-way diff +
  severity + ignore rules), CLI reconcile/probe commands. All gates green.`