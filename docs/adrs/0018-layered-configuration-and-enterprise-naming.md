# ARCHITECTURE DECISION RECORD
## Industry Standard Format for ADRs (2026)

## Document Identification
- **ADR ID**: 018
- **Title**: Layered configuration system and RapidWebs enterprise naming conventions
- **Status**: Proposed (implementation deferred — captured to prevent loss)
- **Date**: 2026-08-28
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

- **Problem Statement**: `rw_blueprint` currently has **no configuration system** — every
  knob (probe timeout, severity overrides, ignore-rule paths, MCP transport) would be
  hardcoded or passed ad-hoc as CLI flags. RapidWebs already has an in-house, proven
  layered-configuration pattern across four projects (`rw_exfil`, `rw_codegate`,
  `rw-telebot`, `NexusAgent`), and `rw_blueprint` must conform to it rather than invent a
  fifth variant. Separately, `rw_blueprint` must adopt the enterprise's consistent variable
  naming conventions (`rw_`/`RW_` prefixes and the env-var nesting delimiter) so config is
  predictable across the RapidWebs toolchain.
- **Drivers**:
  - The user explicitly requested a layered configuration system: *"pydantic defaults →
    project safe defaults (`./config/`) → user custom config (`~/.rw_blueprint/config/`) →
    environment variables (`.env`/shell) → CLI overrides."*
  - The user requested conformance to *"rapidwebs enterprise consistent coding conventions
    for naming variables (RW_, rw_, etc.) ... including a proper convention for nesting
    variables at the env variable layer."*
  - House precedent (verified in source): `rw_codegate/config.py` documents the exact
    five-tier precedence "CLI > env > config files > defaults" and implements `load()`
    (`config.py:1-9`, `226-247`); `rw_exfil/config/loader.py` implements a three-tier merge
    with an `RW_EXFIL_` prefix and `~/.rw_exfil/config.yaml` (`loader.py:5-9`, `64`);
    `rw-telebot/configs/env_loader.py` implements `RW_TELEBOT_` prefixing with `__`
    (double-underscore) nesting (`env_loader.py:21`, `34-44`); `NexusAgent` ADR-0003
    endorses `BaseSettings` + `env_prefix` (`0003-project-branding-config.md:41-43`).
- **Assumptions**: Configuration is for the tool's *runtime behavior* (not the topology
  model — `topology.yaml` remains the source of truth and is NOT folded into the settings
  config). Secrets continue to be referenced by name, never held in config files.
- **Constraints**: MIT license; Python 3.11+; must not add a heavy framework dependency
  when `pydantic-settings` (an official Pydantic sub-package) suffices. The config layer
  must never weaken the emit-untrusted/apply-gated boundary (ADR-011).

## 2. Decision

- **Decision Statement**:
  1. **Adopt a five-tier layered configuration system** with precedence (highest first):
     `CLI arguments > environment variables > user config (~/.rw_blueprint/config.yaml)
     > project defaults (./config/) > Pydantic defaults`. This is realized via
     `pydantic-settings` (`BaseSettings` + `SettingsConfigDict`), which natively provides
     env-var binding, `.env` loading, and typed coercion — the modern successor to the
     hand-rolled loaders in `rw_exfil`/`rw_codegate`/`rw-telebot`.
  2. **Environment-variable contract** — RapidWebs enterprise naming:
     - **Prefix**: `RW_BLUEPRINT_` (uppercase, project name suffix; matches `RW_EXFIL_`,
       `RW_CODEGATE_`, `RW_TELEBOT_`).
     - **Nesting delimiter**: `__` (double underscore) marks a nested-key boundary;
       single underscore is a word separator within a key. Example:
       `RW_BLUEPRINT_PROBE__TIMEOUT` → `probe.timeout`. This is the pydantic-settings
       default (`env_nested_delimiter="__"`) and matches rw-telebot precedent.
     - **Case**: env keys UPPER_SNAKE; config keys lower_snake.
  3. **Project/package naming**: directory and import package remain `rw_blueprint`
     (lowercase `rw_` prefix, underscore separator), consistent with `rw_exfil`,
     `rw_codegate`, `rw_telebot`. Internal identifiers use `rw_` / snake_case; the env
     layer uses the `RW_` / UPPER_SNAKE projection of the same name.
- **Considered Alternatives**:
  - **Alternative 1 — Hand-rolled loader (rw_exfil/rw_codegate/rw-telebot style)**:
    - **Pros**: Zero new dependency; full control.
    - **Cons**: Three divergent in-house implementations already exist — a fourth
      hand-rolled variant perpetuates the exact inconsistency this ADR exists to end;
      manual type coercion and env-map maintenance are error-prone.
  - **Alternative 2 — No config system (status quo)**:
    - **Pros**: Simplest.
    - **Cons**: Hardcodes every knob; breaks the layered-override model the enterprise
      already standardizes; the P5 agent cannot be reconfigured without code changes.
  - **Alternative 3 — Heavy config framework (Dynaconf/Hydra/OmegaConf)**:
    - **Pros**: Rich features (compose, plugins, merge strategies).
    - **Cons**: Adds a dependency and conceptual surface disproportionate to the need;
      `pydantic-settings` covers env + `.env` + typed validation natively.
- **Decision Rationale**: `pydantic-settings` is the official, typed successor that
  subsumes the four hand-rolled loaders' intent with less code and better validation, and
  its native `env_prefix`/`env_nested_delimiter` semantics give us the enterprise naming
  contract *for free*. Adopting the house conventions (rather than a fifth variant) makes
  `rw_blueprint` operationally predictable alongside `rw_exfil`/`rw_codegate`/`rw-telebot`.
- **Implementation Approach** (deferred): Add `pydantic-settings` to `dependencies`; define
  a `Settings` model in `src/rw_blueprint/config.py` with `SettingsConfigDict(
  env_prefix="RW_BLUEPRINT_", env_nested_delimiter="__", env_file=".env", extra="forbid")`;
  wire CLI flags to override `Settings` fields at the highest tier; ship `./config/` with
  safe project defaults and document `~/.rw_blueprint/config.yaml` as the user override.

## 3. Status

Proposed — implementation deferred. This ADR is recorded now so the decision and naming
contract are not lost; the implementation is sequenced after the "now" tier (ADR-013/015/017)
because the config layer is a cross-cutting refactor, not a feature.

## 4. Consequences

### 4.1 Positive Consequences
- One typed, validated config model; no fourth hand-rolled loader.
- `RW_BLUEPRINT_*` env vars are predictable and interoperable with the RapidWebs toolchain.
- `__` nesting is unambiguous and matches pydantic-settings defaults.
- Config is layered so the P5 agent / CI / humans can each override at the right tier.

### 4.2 Negative Consequences
- Adds `pydantic-settings` (small, official) to the dependency set.
- Requires a one-time refactor to thread `Settings` through the CLI/registry/reconciler.

### 4.3 Neutral Consequences
- `topology.yaml` and the topology/live-state/report schemas are unaffected; config governs
  *runtime behavior*, not the source of truth.

## 5. Implications

### 5.1 Architectural Implications
Introduces a runtime `Settings` model and a single `get_settings()` accessor, consumed by
the CLI and (eventually) the MCP server. It is distinct from the declarative topology model.

### 5.2 Technical Implications
`pydantic-settings` dependency; a `config.py`; `./config/` defaults; `--help` surfacing of
env-var bindings; config-merge tests.

### 5.3 Organizational Implications
Documents the canonical RapidWebs env-var naming (`RW_<PROJECT>_` + `__` nesting) that all
future tools should follow.

### 5.4 Financial Implications
None.

### 5.5 Schedule Implications
Deferred; sequenced after the "now" tier (MCP + JSON + remediation). Recorded here so it is
not forgotten.

## 6. Related Documents
- **Supersedes**: None
- **Superseded By**: None
- **Related To**: ADR-003 (Python stack), ADR-013 (MCP surface), ADR-017 (machine-readable report)
- **Amends**: None
- **Referenced By**: `rw_exfil/config/loader.py`, `rw_codegate/config.py`,
  `rw-telebot/configs/env_loader.py`, `NexusAgent/docs/adrs/0003-project-branding-config.md`

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
