"""Layered configuration system for rw_blueprint (ADR-0018).

Five-tier precedence (highest first):
1. CLI arguments
2. Environment variables (RW_BLUEPRINT_ prefix, __ nesting)
3. User config (~/.rw_blueprint/config.yaml)
4. Project defaults (./config/defaults.yaml)
5. Pydantic field defaults

Usage:
    from rw_blueprint.config import get_settings

    settings = get_settings()
    timeout = settings.probe_timeout

Environment variable contract (RapidWebs enterprise):
    RW_BLUEPRINT_PROBE__TIMEOUT → settings.probe.timeout
    RW_BLUEPRINT_DNS__DOMAINS   → settings.dns.domains (JSON list)
    RW_BLUEPRINT_OUTPUT__DIR    → settings.output.dir
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# ── Sub-models ───────────────────────────────────────────────────────────────


class ProbeSettings(BaseModel):
    """Probe execution settings."""

    model_config = ConfigDict(extra="forbid")

    timeout: int = Field(default=10, ge=1, le=300, description="Command timeout in seconds")
    enabled: list[str] = Field(
        default=["incus", "podman", "port", "dns", "tailscale"],
        description="Probes to run by default (all if empty)",
    )


class DnsSettings(BaseModel):
    """DNS probe settings."""

    model_config = ConfigDict(extra="forbid")

    domains: list[str] = Field(
        default=["rapidwebs.org", "infra.rapidwebs.org"],
        description="Domains to resolve during DNS probe",
    )


class HostSettings(BaseModel):
    """Host identification settings."""

    model_config = ConfigDict(extra="forbid")

    default_node: str = Field(
        default="srv1",
        description="Default hostname for probes that run locally",
    )


class OutputSettings(BaseModel):
    """Output defaults."""

    model_config = ConfigDict(extra="forbid")

    dir: str = Field(default="generated/", description="Default output directory for generate")
    format: str = Field(
        default="table", description="Default reconcile output format (table, json, summary)"
    )


class ReconcileSettings(BaseModel):
    """Reconciliation defaults."""

    model_config = ConfigDict(extra="forbid")

    fail_on: str = Field(
        default="critical", description="Default severity threshold (critical, warning, info, none)"
    )


class SeverityWeights(BaseModel):
    """Severity ordering for exit-code computation."""

    model_config = ConfigDict(extra="forbid")

    critical: int = Field(default=3, ge=0)
    warning: int = Field(default=2, ge=0)
    info: int = Field(default=1, ge=0)
    none: int = Field(default=0, ge=0)


# ── Root settings ────────────────────────────────────────────────────────────


class Settings(BaseSettings):
    """Root configuration for rw_blueprint.

    Five-tier precedence: CLI > env > user config > project defaults > field defaults.
    """

    model_config = SettingsConfigDict(
        env_prefix="RW_BLUEPRINT_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
        # YAML config files are loaded manually below, not via pydantic-settings
    )

    probe: ProbeSettings = Field(default_factory=ProbeSettings)
    dns: DnsSettings = Field(default_factory=DnsSettings)
    host: HostSettings = Field(default_factory=HostSettings)
    output: OutputSettings = Field(default_factory=OutputSettings)
    reconcile: ReconcileSettings = Field(default_factory=ReconcileSettings)
    severity_weights: SeverityWeights = Field(default_factory=SeverityWeights)

    # ── Factory methods ──────────────────────────────────────────────────

    @classmethod
    def from_yaml(cls, path: str | Path) -> Settings:
        """Load settings from a YAML file, overlaying on defaults."""
        settings = cls()
        try:
            raw = yaml.safe_load(Path(path).read_text())
            if raw and isinstance(raw, dict):
                settings = cls._merge_dict(settings, raw)
        except (FileNotFoundError, yaml.YAMLError):
            pass  # Missing/malformed file → use defaults
        return settings

    @classmethod
    def load(cls, cli_overrides: dict[str, Any] | None = None) -> Settings:
        """Load settings with full five-tier precedence.

        Tier order (lowest → highest):
        1. Pydantic field defaults (already set)
        2. Project defaults (./config/defaults.yaml)
        3. User config (~/.rw_blueprint/config.yaml)
        4. Environment variables (RW_BLUEPRINT_*)
        5. CLI overrides
        """
        settings = cls()

        # Tier 2: Project defaults
        project_path = Path("config/defaults.yaml")
        if project_path.exists():
            settings = cls.from_yaml(project_path)

        # Tier 3: User config
        user_path = Path.home() / ".rw_blueprint" / "config.yaml"
        if user_path.exists():
            user_settings = cls.from_yaml(user_path)
            settings = cls._merge(settings, user_settings)

        # Tier 4: Environment variables (pydantic-settings handles this natively)
        env_settings = cls()  # reads RW_BLUEPRINT_* from os.environ
        settings = cls._merge(settings, env_settings)

        # Tier 5: CLI overrides
        if cli_overrides:
            settings = cls._apply_cli(settings, cli_overrides)

        return settings

    # ── Merge helpers ────────────────────────────────────────────────────

    @staticmethod
    def _merge(base: Settings, overlay: Settings) -> Settings:
        """Merge overlay into base (overlay wins on non-default values)."""
        merged = base.model_copy(deep=True)
        for field_name in type(base).model_fields:
            base_val = getattr(base, field_name)
            overlay_val = getattr(overlay, field_name)
            if isinstance(base_val, BaseModel) and isinstance(overlay_val, BaseModel):
                # Recursive merge for nested models
                merged_val = base_val.model_copy(deep=True)
                for sub_field in type(base_val).model_fields:
                    ov = getattr(overlay_val, sub_field)
                    bv = getattr(base_val, sub_field)
                    # Only override if overlay differs from its own default
                    if ov != getattr(type(overlay_val)(), sub_field):
                        setattr(merged_val, sub_field, ov)
                    else:
                        setattr(merged_val, sub_field, bv)
                setattr(merged, field_name, merged_val)
            elif overlay_val != getattr(type(base)(), field_name):
                setattr(merged, field_name, overlay_val)
        return merged

    @staticmethod
    def _merge_dict(settings: Settings, raw: dict[str, Any]) -> Settings:
        """Merge a raw dict into settings (for YAML loading)."""
        for key, value in raw.items():
            if hasattr(settings, key):
                existing = getattr(settings, key)
                if isinstance(existing, BaseModel) and isinstance(value, dict):
                    # Merge dict into nested model
                    merged = existing.model_copy(deep=True)
                    for sub_key, sub_val in value.items():
                        if hasattr(merged, sub_key):
                            setattr(merged, sub_key, sub_val)
                    setattr(settings, key, merged)
                else:
                    setattr(settings, key, value)
        return settings

    @staticmethod
    def _apply_cli(settings: Settings, overrides: dict[str, Any]) -> Settings:
        """Apply CLI overrides at highest precedence."""
        for key, value in overrides.items():
            if value is None:
                continue
            # Support dotted keys: "probe.timeout" → settings.probe.timeout
            if "." in key:
                parts = key.split(".")
                target = settings
                for part in parts[:-1]:
                    target = getattr(target, part)
                setattr(target, parts[-1], value)
            elif hasattr(settings, key):
                setattr(settings, key, value)
        return settings


# ── Singleton accessor ───────────────────────────────────────────────────────

_settings: Settings | None = None


def get_settings(cli_overrides: dict[str, Any] | None = None) -> Settings:
    """Return the global Settings singleton, loading on first call."""
    global _settings
    if _settings is None or cli_overrides is not None:
        _settings = Settings.load(cli_overrides)
    return _settings


def reset_settings() -> None:
    """Reset the cached settings (useful for testing)."""
    global _settings
    _settings = None
