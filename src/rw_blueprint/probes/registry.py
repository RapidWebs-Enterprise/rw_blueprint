"""Probe registry - in-process registry of all probes (ADR-0010).

The registry manages probe discovery, execution, and fragment aggregation.
It is intentionally simple — no plugin framework, no dynamic loading.
"""

from __future__ import annotations

from rw_blueprint.live_state import LiveStateFragment
from rw_blueprint.probes.base import Probe, ProbeResult
from rw_blueprint.probes.dns import DnsProbe
from rw_blueprint.probes.incus import IncusProbe
from rw_blueprint.probes.podman import PodmanProbe
from rw_blueprint.probes.port import PortProbe
from rw_blueprint.probes.tailscale import TailscaleProbe


class ProbeRegistry:
    """In-process registry of all probes (ADR-0010).

    The registry manages probe discovery, execution, and fragment aggregation.
    It is intentionally simple — no plugin framework, no dynamic loading.
    """

    def __init__(self, probes: list[Probe] | None = None):
        self._probes = probes or self._default_probes()

    def _default_probes(self) -> list[Probe]:
        return [
            IncusProbe(),
            PodmanProbe(),
            PortProbe(),
            DnsProbe(),
            TailscaleProbe(),
        ]

    def names(self) -> list[str]:
        return [p.name for p in self._probes]

    def get(self, name: str) -> Probe | None:
        for p in self._probes:
            if p.name == name:
                return p
        return None

    def run_all(self) -> tuple[LiveStateFragment, dict[str, ProbeResult]]:
        """Run all probes and aggregate their fragments."""
        combined = LiveStateFragment()
        results: dict[str, ProbeResult] = {}

        for probe in self._probes:
            result = probe.run()
            results[probe.name] = result
            combined = combined.merge(result.fragment)

        return combined, results

    def run_selected(self, names: list[str]) -> tuple[LiveStateFragment, dict[str, ProbeResult]]:
        """Run only the named probes."""
        combined = LiveStateFragment()
        results: dict[str, ProbeResult] = {}

        for name in names:
            probe = self.get(name)
            if probe is None:
                results[name] = ProbeResult(
                    name=name,
                    fragment=LiveStateFragment(),
                    errors=[f"unknown probe: {name}"],
                    duration_ms=0,
                )
                continue
            result = probe.run()
            results[name] = result
            combined = combined.merge(result.fragment)

        return combined, results
