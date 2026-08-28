"""Tailscale probe - observes Tailscale mesh via ``tailscale status --json``."""

from __future__ import annotations

import json
from datetime import datetime

from rw_blueprint.live_state import LiveLink, LiveNode, LiveStateFragment
from rw_blueprint.probes.base import Probe, ProbeResult


class TailscaleProbe(Probe):
    """Probe Tailscale mesh via ``tailscale status --json``."""

    @property
    def name(self) -> str:
        return "tailscale"

    def run(self) -> ProbeResult:
        start = datetime.now()
        errors: list[str] = []
        fragment = LiveStateFragment()

        exit_code, stdout, stderr = self._run_cmd(["tailscale", "status", "--json"])
        if exit_code != 0:
            errors.append(f"tailscale status failed: {stderr}")
            return ProbeResult(
                name=self.name,
                fragment=fragment,
                errors=errors,
                duration_ms=int((datetime.now() - start).total_seconds() * 1000),
            )

        try:
            status = json.loads(stdout)
        except json.JSONDecodeError as e:
            errors.append(f"failed to parse tailscale JSON: {e}")
            return ProbeResult(
                name=self.name,
                fragment=fragment,
                errors=errors,
                duration_ms=int((datetime.now() - start).total_seconds() * 1000),
            )

        self_node = status.get("Self", {})
        self_name = self_node.get("HostName", "srv1")

        # Add the self node
        fragment.nodes.append(
            LiveNode(
                id=self_name,
                type="host",
                provider="tailscale",
                state="running",
            )
        )

        peers = status.get("Peer", [])
        # Handle both list and dict formats (tailscale JSON can vary)
        if isinstance(peers, dict):
            peers = list(peers.values())

        for peer in peers:
            if not isinstance(peer, dict):
                continue
            peer_name = peer.get("HostName", "")
            online = peer.get("Online", False)

            if not online:
                continue

            # Add the peer node
            fragment.nodes.append(
                LiveNode(
                    id=peer_name,
                    type="host",
                    provider="tailscale",
                    state="running",
                )
            )

            # Create a link representing the mesh connection
            link = LiveLink(
                id=f"tailscale-{self_name}-{peer_name}",
                **{"from": self_name},
                to=peer_name,
                protocol="wireguard",
                observed=True,
            )
            fragment.links.append(link)

        return ProbeResult(
            name=self.name,
            fragment=fragment,
            errors=errors,
            duration_ms=int((datetime.now() - start).total_seconds() * 1000),
        )
