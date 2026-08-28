"""Tests for the probe registry entry-points discovery (ADR-0014)."""

from __future__ import annotations

from importlib import metadata

import pytest

from rw_blueprint.probes.base import Probe, ProbeResult
from rw_blueprint.probes.registry import (
    ENTRY_POINT_GROUP,
    BrokenProbe,
    ProbeRegistry,
)


class _FakeEntryPoint:
    """Minimal EntryPoint-like object for testing."""

    def __init__(self, name: str, value):
        self.name = name
        self._value = value

    def load(self):
        return self._value


class _WorkingProbe(Probe):
    @property
    def name(self) -> str:
        return "fakeworking"

    def run(self) -> ProbeResult:
        from rw_blueprint.live_state import LiveStateFragment

        return ProbeResult(
            name="fakeworking",
            fragment=LiveStateFragment(),
            errors=[],
            duration_ms=1,
        )


def _make_custom_probe(timeout: int = 10, host_node: str = "srv1") -> _WorkingProbe:
    """Factory that returns a probe named 'custom' (matches entry-point name)."""
    return _CustomProbe(timeout=timeout, host_node=host_node)


class _CustomProbe(_WorkingProbe):
    @property
    def name(self) -> str:  # type: ignore[override]
        return "custom"


class _RaisesOnCall:
    """Callable whose call raises — used to simulate entry-point load failure."""

    def __call__(self, *args: object, **kwargs: object) -> None:
        raise RuntimeError("import-time error")


def test_entry_point_group_constant() -> None:
    """The entry-point group is the documented string."""
    assert ENTRY_POINT_GROUP == "rw_blueprint.probes"


def test_broken_probe_reports_error() -> None:
    """BrokenProbe surfaces a diagnostic error, never raises."""
    broken = BrokenProbe(name="badprobe", error="synthetic failure")
    result = broken.run()
    assert result.name == "badprobe"
    assert "broken probe: synthetic failure" in result.errors


def test_registry_includes_default_probes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Registry returns the five core in-process probes by default."""
    # Patch entry_points to return empty (no third-party)
    monkeypatch.setattr(metadata, "entry_points", lambda group: [])

    registry = ProbeRegistry(discover_entry_points=True)
    names = registry.names()
    assert "incus" in names
    assert "podman" in names
    assert "port" in names
    assert "dns" in names
    assert "tailscale" in names


def test_registry_discovers_third_party_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    """A working entry-point probe (factory) is discovered and registered."""

    def fake_eps(group: str) -> list[_FakeEntryPoint]:
        if group == ENTRY_POINT_GROUP:
            return [_FakeEntryPoint(name="custom", value=_make_custom_probe)]
        return []

    monkeypatch.setattr(metadata, "entry_points", fake_eps)

    registry = ProbeRegistry(discover_entry_points=True)
    # The probe's own .name property is its identity (ADR-0010)
    assert "custom" in registry.names()
    probe = registry.get("custom")
    assert probe is not None
    assert isinstance(probe, _CustomProbe)


def test_registry_broken_entry_point_becomes_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failing entry point surfaces as BrokenProbe, not a crash."""

    def fake_eps(group: str) -> list[_FakeEntryPoint]:
        if group == ENTRY_POINT_GROUP:
            return [_FakeEntryPoint(name="bad", value=_RaisesOnCall())]
        return []

    monkeypatch.setattr(metadata, "entry_points", fake_eps)

    registry = ProbeRegistry(discover_entry_points=True)
    probe = registry.get("bad")
    assert probe is not None
    assert isinstance(probe, BrokenProbe)
    result = probe.run()
    assert any("broken probe" in e for e in result.errors)


def test_registry_inprocess_wins_on_name_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    """In-process probes take precedence over entry-point duplicates."""
    from rw_blueprint.probes.dns import DnsProbe

    def fake_eps(group: str) -> list[_FakeEntryPoint]:
        # Try to override "dns" with a different probe
        return [_FakeEntryPoint(name="dns", value=_make_custom_probe)]

    monkeypatch.setattr(metadata, "entry_points", fake_eps)
    registry = ProbeRegistry(discover_entry_points=True)
    dns = registry.get("dns")
    # In-process wins — the resolved probe is the built-in DnsProbe, not _CustomProbe
    assert dns is not None
    assert isinstance(dns, DnsProbe)
    assert not isinstance(dns, _CustomProbe)


def test_registry_discover_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """discover_entry_points=False skips entry-point enumeration."""
    called = {"yes": False}

    def fake_eps(group: str):
        called["yes"] = True
        return []

    monkeypatch.setattr(metadata, "entry_points", fake_eps)
    ProbeRegistry(discover_entry_points=False)
    assert called["yes"] is False


def test_registry_explicit_probes_override() -> None:
    """Probes passed to constructor override discovered probes by name."""
    registry = ProbeRegistry(probes=[_WorkingProbe()], discover_entry_points=False)
    # _WorkingProbe has name "fakeworking" — it should be registered
    assert "fakeworking" in registry.names()


def test_broken_entry_point_metadata_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """If entry_points() itself raises, the registry handles it gracefully."""

    def boom(group: str):
        raise RuntimeError("metadata backend unavailable")

    monkeypatch.setattr(metadata, "entry_points", boom)
    # Should not raise
    registry = ProbeRegistry(discover_entry_points=True)
    # Core probes still present
    assert "incus" in registry.names()
