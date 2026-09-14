"""Incus probe - observes Incus containers via `incus list --format json`.

Supports both local and remote (SSH) execution.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Literal

from rw_blueprint.live_state import LiveNode, LiveStateFragment
from rw_blueprint.probes.base import Probe, ProbeResult
from rw_blueprint.probes.ssh import run_local_cmd, run_remote_cmd

_logger = logging.getLogger(__name__)


class IncusProbe(Probe):
    """Probe Incus containers via `incus list --format json`."""

    @property
    def name(self) -> str:
        return "incus"

    def run(self) -> ProbeResult:
        start = datetime.now()
        errors: list[str] = []
        fragment = LiveStateFragment()

        # Try local incus first, then remote via SSH
        exit_code, stdout, stderr = run_local_cmd(["incus", "list", "--format", "json"])

        if exit_code != 0:
            # Fall back to remote SSH access
            _logger.info("Local incus failed, trying SSH to %s", self.host_node)
            exit_code, stdout, stderr = run_remote_cmd(
                self.host_node,
                ["incus", "list", "--format", "json"],
                timeout=self.timeout,
            )

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
