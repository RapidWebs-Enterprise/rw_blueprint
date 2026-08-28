"""Incus probe - observes Incus containers via ``incus list --format json``."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Literal

from rw_blueprint.live_state import LiveNode, LiveStateFragment
from rw_blueprint.probes.base import Probe, ProbeResult


class IncusProbe(Probe):
    """Probe Incus containers via ``incus list --format json``."""

    @property
    def name(self) -> str:
        return "incus"

    def run(self) -> ProbeResult:
        start = datetime.now()
        errors: list[str] = []
        fragment = LiveStateFragment()

        exit_code, stdout, stderr = self._run_cmd(["incus", "list", "--format", "json"])
        if exit_code != 0:
            errors.append(f"incus list failed: {stderr}")
            return ProbeResult(
                name=self.name,
                fragment=fragment,
                errors=errors,
                duration_ms=int((datetime.now() - start).total_seconds() * 1000),
            )

        try:
            containers = json.loads(stdout)
        except json.JSONDecodeError as e:
            errors.append(f"failed to parse incus JSON: {e}")
            return ProbeResult(
                name=self.name,
                fragment=fragment,
                errors=errors,
                duration_ms=int((datetime.now() - start).total_seconds() * 1000),
            )

        for c in containers:
            name = c.get("name", "")
            status = c.get("status", "unknown")
            state: Literal["running", "stopped", "frozen", "unknown"] = (
                "running" if status == "Running" else "stopped"
            )

            # Extract IPs
            public_ip = None
            tailscale_ip = None
            for net in c.get("devices", {}).values():
                if net.get("type") == "nic":
                    ipv4 = net.get("ipv4.address")
                    if ipv4 and not ipv4.startswith("100."):
                        public_ip = ipv4
                    elif ipv4 and ipv4.startswith("100."):
                        tailscale_ip = ipv4

            node = LiveNode(
                id=name,
                type="container",
                provider="incus",
                public_ip=public_ip,
                tailscale_ip=tailscale_ip,
                state=state,
            )
            fragment.nodes.append(node)

        return ProbeResult(
            name=self.name,
            fragment=fragment,
            errors=errors,
            duration_ms=int((datetime.now() - start).total_seconds() * 1000),
        )
