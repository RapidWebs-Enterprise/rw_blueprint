"""DNS probe - observes DNS resolution via ``kdig`` or ``dig``.

Supports both local and remote (SSH) execution.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from rw_blueprint.live_state import LiveLink, LiveNode, LiveStateFragment
from rw_blueprint.probes.base import Probe, ProbeResult
from rw_blueprint.probes.ssh import run_local_cmd, run_remote_cmd

if TYPE_CHECKING:
    from rw_blueprint.live_state import LiveStateFragment

_logger = logging.getLogger(__name__)


class DnsProbe(Probe):
    """Probe DNS resolution via ``kdig`` or ``dig``."""

    @property
    def name(self) -> str:
        return "dns"

    def __init__(
        self, domains: list[str] | None = None, timeout: int = 10, host_node: str = "srv1"
    ):
        super().__init__(timeout=timeout, host_node=host_node)
        self.domains = domains or ["rapidwebs.org", "infra.rapidwebs.org"]

    def run(self) -> ProbeResult:
        start = datetime.now()
        errors: list[str] = []
        fragment = LiveStateFragment()

        # Add the host node that DNS queries originate from
        fragment.nodes.append(
            LiveNode(
                id=self.host_node,
                type="host",
                provider="local",
                state="running",
            )
        )

        for domain in self.domains:
            # Add the DNS target as an external node
            dns_node_id = f"dns:{domain}"
            fragment.nodes.append(
                LiveNode(
                    id=dns_node_id,
                    type="external",
                    provider="dns",
                    state="running",
                )
            )

            # Try kdig first, fall back to dig
            success = False
            for cmd in [["kdig", "+short", domain], ["dig", "+short", domain]]:
                exit_code, stdout, stderr = run_local_cmd(cmd)

                if exit_code != 0:
                    # Try via SSH
                    _logger.info("DNS query failed locally, trying SSH to %s", self.host_node)
                    exit_code, stdout, stderr = run_remote_cmd(
                        self.host_node,
                        cmd,
                        timeout=self.timeout,
                    )

                if exit_code == 0:
                    # Success - kdig/dig returned exit 0 (DNS query executed)
                    # Empty stdout means no A record, but NS/SOA may exist
                    link = LiveLink(
                        id=f"dns-{domain}",
                        **{"from": self.host_node},
                        to=dns_node_id,
                        protocol="dns",
                        observed=True,
                    )
                    fragment.links.append(link)
                    success = True
                    break

            if not success:
                errors.append(f"DNS resolution failed for {domain}")

        return ProbeResult(
            name=self.name,
            fragment=fragment,
            errors=errors,
            duration_ms=int((datetime.now() - start).total_seconds() * 1000),
        )
