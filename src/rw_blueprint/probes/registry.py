"""Probe registry - in-process + entry-points discovery (ADR-0010, ADR-0014).

The registry manages probe discovery, execution, and fragment aggregation.

Discovery order (ADR-0014):
1. In-process core probes (auditable default)
2. Third-party probes discovered via `importlib.metadata.entry_points`
   in the ``rw_blueprint.probes`` group
3. Probes passed explicitly via constructor

In-process probes win on name conflicts (logged). Broken third-party probes
are surfaced as diagnostic ``BrokenProbe`` instances — they never crash the CLI.
"""

from __future__ import annotations

import logging
from importlib import metadata
from typing import TYPE_CHECKING

from rw_blueprint.live_state import LiveStateFragment
from rw_blueprint.probes.base import Probe, ProbeResult
from rw_blueprint.probes.dns import DnsProbe
from rw_blueprint.probes.incus import IncusProbe
from rw_blueprint.probes.podman import PodmanProbe
from rw_blueprint.probes.port import PortProbe
from rw_blueprint.probes.tailscale import TailscaleProbe

if TYPE_CHECKING:
    pass

_logger = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "rw_blueprint.probes"


class BrokenProbe(Probe):
    """Diagnostic probe that records a load failure.

    Used when a third-party probe fails to import or instantiate. This
    implements the click-plugins ``BrokenCommand`` pattern: a broken plugin
    degrades gracefully, never crashes the CLI.
    """

    def __init__(self, name: str, error: str, host_node: str = "srv1"):
        super().__init__(timeout=10, host_node=host_node)
        self._name = name
        self._error = error

    @property
    def name(self) -> str:
        return self._name

    def run(self) -> ProbeResult:
        start_fragment = LiveStateFragment()
        return ProbeResult(
            name=self._name,
            fragment=start_fragment,
            errors=[f"broken probe: {self._error}"],
            duration_ms=0,
        )


class ProbeRegistry:
    """In-process + entry-points registry of all probes (ADR-0010, ADR-0014).

    Discovery order (first wins on name conflict):
    1. In-process core probes
    2. Third-party entry-point probes
    3. Probes passed explicitly to constructor
    """

    def __init__(
        self,
        probes: list[Probe] | None = None,
        timeout: int = 10,
        host_node: str = "srv1",
        discover_entry_points: bool = True,
    ):
        self._timeout = timeout
        self._host_node = host_node
        self._probes = self._discover(
            timeout=timeout,
            host_node=host_node,
            discover_entry_points=discover_entry_points,
        )
        # User-supplied probes override discovered (by name)
        if probes:
            known_names = {p.name for p in self._probes}
            for p in probes:
                if p.name in known_names:
                    _logger.debug("probe %r overridden by explicit instance", p.name)
                    self._probes = [p if e.name == p.name else e for e in self._probes]
                else:
                    self._probes.append(p)

    def _discover(self, timeout: int, host_node: str, discover_entry_points: bool) -> list[Probe]:
        """Discover probes: in-process first, then entry-points."""
        probes = self._in_process(timeout=timeout, host_node=host_node)
        if discover_entry_points:
            probes.extend(self._from_entry_points(timeout=timeout, host_node=host_node))
        return probes

    def _in_process(self, timeout: int, host_node: str) -> list[Probe]:
        """The five core probes — always present, always auditable."""
        return [
            IncusProbe(timeout=timeout, host_node=host_node),
            PodmanProbe(timeout=timeout, host_node=host_node),
            PortProbe(timeout=timeout, host_node=host_node),
            DnsProbe(timeout=timeout, host_node=host_node),
            TailscaleProbe(timeout=timeout, host_node=host_node),
        ]

    def _from_entry_points(self, timeout: int, host_node: str) -> list[Probe]:
        """Discover third-party probes via importlib.metadata entry points.

        The entry-point value is a callable that returns a Probe instance:
        ``entry_point.load()()`` must produce a Probe (or be a Probe class).
        Broken entry points surface as ``BrokenProbe`` diagnostics.
        """
        discovered: list[Probe] = []
        try:
            eps = metadata.entry_points(group=ENTRY_POINT_GROUP)
        except Exception as exc:
            _logger.warning("failed to enumerate entry points: %s", exc)
            return discovered

        for ep in eps:
            try:
                loaded = ep.load()
                probe = self._instantiate(loaded, timeout=timeout, host_node=host_node)
            except Exception as exc:
                _logger.warning("entry point %r failed to load: %s", ep.name, exc)
                discovered.append(BrokenProbe(name=ep.name, error=str(exc), host_node=host_node))
                continue

            if isinstance(probe, Probe):
                discovered.append(probe)
            else:
                err = f"entry point did not return a Probe (got {type(probe).__name__})"
                discovered.append(BrokenProbe(name=ep.name, error=err, host_node=host_node))
        return discovered

    @staticmethod
    def _instantiate(loaded: object, timeout: int, host_node: str) -> object:
        """Instantiate an entry-point probe, passing config when accepted.

        Supports both Probe classes (call with config) and factories (call with no args).
        Probes that don't accept config keywords are instantiated with no args.
        """
        if callable(loaded) and isinstance(loaded, type):
            # Class — try config-aware ctor, fall back to no-arg
            try:
                return loaded(timeout=timeout, host_node=host_node)
            except TypeError:
                return loaded()
        if callable(loaded):
            # Factory — call with no args
            return loaded()
        return loaded

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
