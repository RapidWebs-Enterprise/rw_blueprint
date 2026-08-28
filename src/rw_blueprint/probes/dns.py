"""DNS probe - observes DNS resolution via ``kdig`` or ``dig``."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from rw_blueprint.live_state import LiveLink, LiveNode, LiveStateFragment
from rw_blueprint.probes.base import Probe, ProbeResult

if TYPE_CHECKING:
    from rw_blueprint.live_state import LiveStateFragment


class DnsProbe(Probe):
    """Probe DNS resolution via ``kdig`` or ``dig``."""

    @property
    def name(self) -> str:
        return "dns"

    def __init__(self, domains: list[str] | None = None):
        self.domains = domains or ["rapidwebs.org", "infra.rapidwebs.org"]

    def run(self) -> ProbeResult:
        start = datetime.now()
        errors: list[str] = []
        fragment = LiveStateFragment()

        # Add the host node that DNS queries originate from
        fragment.nodes.append(
            LiveNode(
                id="srv1",
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
            for cmd in [["kdig", "+short", domain], ["dig", "+short", domain]]:
                exit_code, stdout, stderr = self._run_cmd(cmd)
                if exit_code == 0 and stdout.strip():
                    # Success - create a link showing DNS resolution works
                    link = LiveLink(
                        id=f"dns-{domain}",
                        **{"from": "srv1"},
                        to=dns_node_id,
                        protocol="dns",
                        observed=True,
                    )
                    fragment.links.append(link)
                    break
            else:
                errors.append(f"DNS resolution failed for {domain}")

        return ProbeResult(
            name=self.name,
            fragment=fragment,
            errors=errors,
            duration_ms=int((datetime.now() - start).total_seconds() * 1000),
        )
