"""Multi-target probe coordinator for distributed infrastructure.

This module allows probes to run against multiple target nodes and merge
their results into a unified live-state fragment.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from rw_blueprint.live_state import LiveStateFragment
from rw_blueprint.probes.base import Probe, ProbeResult

if TYPE_CHECKING:
    pass

_logger = logging.getLogger(__name__)


@dataclass
class TargetNode:
    """A target node to probe."""

    id: str
    type: str = "host"
    ssh_host: str | None = None  # hostname or IP for SSH
    ssh_user: str = "sysop"
    timeout: int = 10


class MultiNodeProbeCoordinator:
    """Coordinate probes across multiple target nodes.

    Runs each probe against each target node and merges results.
    Handles SSH fallback for remote nodes.
    """

    def __init__(
        self,
        targets: list[TargetNode] | None = None,
        default_timeout: int = 10,
    ):
        self.targets = targets or []
        self.default_timeout = default_timeout

    def add_target(self, target: TargetNode) -> None:
        """Add a target node to probe."""
        self.targets.append(target)

    def run_probe_on_targets(
        self,
        probe_factory,
        probe_name: str,
    ) -> tuple[LiveStateFragment, dict[str, ProbeResult]]:
        """Run a probe against all target nodes and merge results.

        Args:
            probe_factory: A callable that creates a Probe instance given (timeout, host_node)
            probe_name: Name of the probe for logging

        Returns:
            Tuple of (merged fragment, dict of per-target results)
        """
        merged = LiveStateFragment()
        results: dict[str, ProbeResult] = {}

        for target in self.targets:
            ssh_host = target.ssh_host or target.id
            try:
                probe = probe_factory(
                    timeout=target.timeout,
                    host_node=ssh_host,
                )
                result = probe.run()
                results[target.id] = result
                merged = merged.merge(result.fragment)
                _logger.debug(
                    "Probe %s on %s: %d nodes, %d services, %d errors",
                    probe_name,
                    target.id,
                    len(result.fragment.nodes),
                    len(result.fragment.services),
                    len(result.errors),
                )
            except Exception as e:
                _logger.warning("Probe %s on %s failed: %s", probe_name, target.id, e)
                results[target.id] = ProbeResult(
                    name=probe_name,
                    fragment=LiveStateFragment(),
                    errors=[f"probe failed: {e}"],
                    duration_ms=0,
                )

        return merged, results

    def get_target_for_node(self, node_id: str) -> TargetNode | None:
        """Get the target config for a node ID."""
        for target in self.targets:
            if target.id == node_id:
                return target
        return None
