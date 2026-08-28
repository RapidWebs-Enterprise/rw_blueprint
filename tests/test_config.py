"""Tests for the layered configuration system (ADR-0018)."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from rw_blueprint.config import (
    ProbeSettings,
    Settings,
    get_settings,
    reset_settings,
)


class TestSettingsDefaults:
    """Verify Pydantic field defaults (Tier 1)."""

    def test_probe_timeout_default(self) -> None:
        reset_settings()
        s = Settings()
        assert s.probe.timeout == 10

    def test_probe_enabled_default(self) -> None:
        reset_settings()
        s = Settings()
        assert "incus" in s.probe.enabled
        assert "tailscale" in s.probe.enabled

    def test_dns_domains_default(self) -> None:
        reset_settings()
        s = Settings()
        assert "rapidwebs.org" in s.dns.domains

    def test_host_default_node(self) -> None:
        reset_settings()
        s = Settings()
        assert s.host.default_node == "srv1"

    def test_output_defaults(self) -> None:
        reset_settings()
        s = Settings()
        assert s.output.dir == "generated/"
        assert s.output.format == "table"

    def test_reconcile_fail_on_default(self) -> None:
        reset_settings()
        s = Settings()
        assert s.reconcile.fail_on == "critical"

    def test_severity_weights_default(self) -> None:
        reset_settings()
        s = Settings()
        assert s.severity_weights.critical == 3
        assert s.severity_weights.warning == 2
        assert s.severity_weights.info == 1


class TestSettingsFromYaml:
    """Verify YAML config loading (Tiers 2-3)."""

    def test_load_project_defaults(self) -> None:
        """Project defaults YAML loads correctly."""
        reset_settings()
        path = Path(__file__).parent.parent / "config" / "defaults.yaml"
        s = Settings.from_yaml(path)
        assert s.probe.timeout == 10
        assert s.host.default_node == "srv1"

    def test_yaml_overrides_field_defaults(self) -> None:
        """YAML values override Pydantic defaults."""
        reset_settings()
        import tempfile

        import yaml

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({"probe": {"timeout": 42}, "host": {"default_node": "custom"}}, f)
            path = f.name

        try:
            s = Settings.from_yaml(path)
            assert s.probe.timeout == 42
            assert s.host.default_node == "custom"
            # Unspecified fields retain defaults
            assert s.output.dir == "generated/"
        finally:
            os.unlink(path)

    def test_missing_yaml_returns_defaults(self) -> None:
        """Missing YAML file returns defaults without error."""
        reset_settings()
        s = Settings.from_yaml("/nonexistent/path.yaml")
        assert s.probe.timeout == 10


class TestSettingsLoad:
    """Verify full five-tier load."""

    def test_load_returns_settings(self) -> None:
        """load() returns a Settings instance."""
        reset_settings()
        s = Settings.load()
        assert isinstance(s, Settings)
        assert s.probe.timeout == 10

    def test_cli_overrides_highest_precedence(self) -> None:
        """CLI overrides win over all other tiers."""
        reset_settings()
        s = Settings.load({"probe.timeout": 99})
        assert s.probe.timeout == 99

    def test_cli_dotted_key_override(self) -> None:
        """Dotted keys like 'probe.timeout' work."""
        reset_settings()
        s = Settings.load({"dns.domains": ["example.com"]})
        assert s.dns.domains == ["example.com"]

    def test_cli_none_skipped(self) -> None:
        """None values in CLI overrides are ignored."""
        reset_settings()
        s = Settings.load({"probe.timeout": None})
        assert s.probe.timeout == 10  # default preserved


class TestEnvVarPrecedence:
    """Verify environment variable binding (Tier 4)."""

    def test_env_var_overrides_default(self) -> None:
        """RW_BLUEPRINT_PROBE__TIMEOUT overrides the default."""
        reset_settings()
        with patch.dict(os.environ, {"RW_BLUEPRINT_PROBE__TIMEOUT": "77"}, clear=True):
            s = Settings()
            assert s.probe.timeout == 77

    def test_env_var_nested_key(self) -> None:
        """Double-underscore maps to nested model field."""
        reset_settings()
        with patch.dict(os.environ, {"RW_BLUEPRINT_HOST__DEFAULT_NODE": "custom-host"}, clear=True):
            s = Settings()
            assert s.host.default_node == "custom-host"

    def test_env_var_list_parsing(self) -> None:
        """JSON list in env var is parsed correctly."""
        reset_settings()
        with patch.dict(
            os.environ,
            {"RW_BLUEPRINT_DNS__DOMAINS": '["a.com","b.com"]'},
            clear=True,
        ):
            s = Settings()
            assert s.dns.domains == ["a.com", "b.com"]


class TestSubModels:
    """Verify sub-model validation."""

    def test_probe_timeout_bounds(self) -> None:
        """Probe timeout must be >= 1."""
        s = ProbeSettings(timeout=1)
        assert s.timeout == 1

    def test_extra_fields_forbidden(self) -> None:
        """Unknown fields are rejected."""
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            ProbeSettings(timeout=10, bogus="nope")  # type: ignore[call-arg]


class TestGetSettings:
    """Verify singleton accessor."""

    def test_get_settings_returns_singleton(self) -> None:
        """get_settings() returns the same instance."""
        reset_settings()
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_get_settings_with_overrides(self) -> None:
        """get_settings with overrides returns a new instance."""
        reset_settings()
        s1 = get_settings()
        s2 = get_settings({"probe.timeout": 55})
        assert s1 is not s2
        assert s2.probe.timeout == 55
