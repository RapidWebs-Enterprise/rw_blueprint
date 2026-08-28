"""Port probe - observes listening ports via ``ss -tlnp --json``."""

from __future__ import annotations

import json
import re
from datetime import datetime

from rw_blueprint.live_state import LiveLink, LiveNode, LiveStateFragment
from rw_blueprint.probes.base import Probe, ProbeResult


class PortProbe(Probe):
    """Probe listening ports via ``ss -tlnp --json``."""

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
                id="srv1",
                type="host",
                provider="local",
                state="running",
            )
        )

        exit_code, stdout, stderr = self._run_cmd(["ss", "-tlnp", "--json"])
        if exit_code != 0:
            errors.append(f"ss failed: {stderr}")
            return ProbeResult(
                name=self.name,
                fragment=fragment,
                errors=errors,
                duration_ms=int((datetime.now() - start).total_seconds() * 1000),
            )

        try:
            listeners = json.loads(stdout)
        except json.JSONDecodeError as e:
            errors.append(f"failed to parse ss JSON: {e}")
            return ProbeResult(
                name=self.name,
                fragment=fragment,
                errors=errors,
                duration_ms=int((datetime.now() - start).total_seconds() * 1000),
            )

        for listener in listeners:
            local_port = listener.get("local_port", 0)
            process = listener.get("process", "")

            # Extract process name from "pid=123,comm=foo"
            proc_name = "unknown"
            if process:
                match = re.search(r"comm=([^,]+)", process)
                if match:
                    proc_name = match.group(1)

            # Add the port as an external node
            port_node_id = f"port:{local_port}"
            fragment.nodes.append(
                LiveNode(
                    id=port_node_id,
                    type="external",
                    provider="port",
                    state="running",
                )
            )

            # Create a link from the host to the port
            link_id = f"port-{local_port}-{proc_name}"
            link = LiveLink(
                id=link_id,
                **{"from": "srv1"},
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
