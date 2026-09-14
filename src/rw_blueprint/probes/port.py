"""Port probe - observes listening ports via ss -tlnp.

Supports both local and remote (SSH) execution.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime

from rw_blueprint.live_state import LiveLink, LiveNode, LiveStateFragment
from rw_blueprint.probes.base import Probe, ProbeResult
from rw_blueprint.probes.ssh import run_local_cmd, run_remote_cmd

_logger = logging.getLogger(__name__)


class PortProbe(Probe):
    """Probe listening ports via ss -tlnp."""

    @property
    def name(self) -> str:
        return "port"

    def run(self) -> ProbeResult:
        start = datetime.now()
        errors: list[str] = []
        fragment = LiveStateFragment()

        # Add the host node that ports are listened on
        fragment.nodes.append(
            LiveNode(
                id=self.host_node,
                type="host",
                provider="local",
                state="running",
            )
        )

        # Try local first, then SSH
        exit_code, stdout, stderr = run_local_cmd(["ss", "-tlnp"])

        if exit_code != 0:
            _logger.info("Local ss failed, trying SSH to %s", self.host_node)
            exit_code, stdout, stderr = run_remote_cmd(
                self.host_node,
                ["ss", "-tlnp"],
                timeout=self.timeout,
            )

        if exit_code != 0:
            errors.append(f"ss failed: {stderr}")
            return ProbeResult(
                name=self.name,
                fragment=fragment,
                errors=errors,
                duration_ms=int((datetime.now() - start).total_seconds() * 1000),
            )

        # Parse text output: State  Recv-Q  Send-Q  Local Address:Port  Peer Address:Port  Process
        for line in stdout.strip().splitlines()[1:]:  # skip header
            parts = line.split()
            if len(parts) < 4:
                continue
            local_addr_port = parts[3]
            # Handle IPv6 format [::]:port or port:port
            if ":" in local_addr_port:
                # Could be IPv4:port or [ipv6]:port
                if local_addr_port.startswith("["):
                    # IPv6: [::]:port
                    match = re.match(r"\[([^\]]+)\]:(\d+)", local_addr_port)
                    if match:
                        port = int(match.group(2))
                    else:
                        continue
                else:
                    # IPv4: 0.0.0.0:port or *:port
                    port = int(local_addr_port.rsplit(":", 1)[1])
            else:
                continue

            # Extract process name from users=(\""name\"",pid=123,fd=1)
            proc_name = "unknown"
            if len(parts) >= 6:
                process_info = " ".join(parts[5:])
                match = re.search(r'users=\(\("\'([^"\'"]+)\',', process_info)
                if match:
                    proc_name = match.group(1)

            # Add the port as an external node
            port_node_id = f"port:{port}"
            fragment.nodes.append(
                LiveNode(
                    id=port_node_id,
                    type="external",
                    provider="port",
                    state="running",
                )
            )

            # Create a link from the host to the port
            link_id = f"port-{port}-{proc_name}"
            link = LiveLink(
                id=link_id,
                **{"from": self.host_node},
                to=port_node_id,
                protocol="tcp",
                observed=True,
            )
            fragment.links.append(link)

        return ProbeResult(
            name=self.name,
            fragment=fragment,
            errors=errors,
            duration_ms=int((datetime.now() - start).total_seconds() * 1000),
        )
