"""Probe registry and built-in probes for rw_blueprint.

This module implements the in-process probe registry (ADR-0010) and the
five built-in probes for the RWDN stack:

* ``incus`` — observes Incus containers (nodes)
* ``podman`` — observes podman containers (services)
* ``port`` — observes listening ports (links)
* ``dns`` — observes DNS resolution health
* ``tailscale`` — observes Tailscale mesh peers (links)

All probes are **read-only by construction** — they execute commands and
parse output, never mutating state. This is the safety property that makes
them safe to run on a heartbeat without HITL.
"""

from __future__ import annotations

import json
import re
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Literal

from rw_blueprint.live_state import (
    LiveLink,
    LiveNode,
    LivePort,
    LiveService,
    LiveStateFragment,
)
from rw_blueprint.schema import ManagedBy, ServiceKind

if TYPE_CHECKING:
    from rw_blueprint.schema import ManagedBy


@dataclass(frozen=True)
class ProbeResult:
    """Result of a probe execution."""

    name: str
    fragment: LiveStateFragment
    errors: list[str]
    duration_ms: int


class Probe(ABC):
    """Abstract base class for all probes."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique probe identifier."""

    @abstractmethod
    def run(self) -> ProbeResult:
        """Execute the probe and return a fragment."""

    def _run_cmd(self, cmd: list[str], timeout: int = 10) -> tuple[int, str, str]:
        """Run a command and return (exit_code, stdout, stderr)."""
        try:
            result = subprocess.run(  # noqa: S603
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"timeout after {timeout}s"
        except FileNotFoundError:
            return -1, "", f"command not found: {cmd[0]}"
        except Exception as e:
            return -1, "", str(e)


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


class PodmanProbe(Probe):
    """Probe podman containers via ``podman ps --format json``."""

    @property
    def name(self) -> str:
        return "podman"

    def run(self) -> ProbeResult:
        start = datetime.now()
        errors: list[str] = []
        fragment = LiveStateFragment()

        exit_code, stdout, stderr = self._run_cmd(["podman", "ps", "--all", "--format", "json"])
        if exit_code != 0:
            errors.append(f"podman ps failed: {stderr}")
            return ProbeResult(
                name=self.name,
                fragment=fragment,
                errors=errors,
                duration_ms=int((datetime.now() - start).total_seconds() * 1000),
            )

        try:
            containers = json.loads(stdout)
        except json.JSONDecodeError as e:
            errors.append(f"failed to parse podman JSON: {e}")
            return ProbeResult(
                name=self.name,
                fragment=fragment,
                errors=errors,
                duration_ms=int((datetime.now() - start).total_seconds() * 1000),
            )

        for c in containers:
            name = c.get("Names", [""])[0].lstrip("/")
            image = c.get("Image", "")
            status = c.get("Status", "").lower()
            state: Literal["running", "stopped", "paused", "unknown"] = (
                "running"
                if "up" in status
                else "stopped"
                if "exited" in status
                else "paused"
                if "paused" in status
                else "unknown"
            )

            # Parse ports
            ports: list[LivePort] = []
            for p in c.get("Ports", []):
                if p.get("PublicPort"):
                    ports.append(
                        LivePort(
                            port=p["PrivatePort"],
                            public=p["PublicPort"],
                            protocol=p.get("Type", "tcp").lower(),
                        )
                    )

            # Determine managed_by from labels
            labels = c.get("Labels", {})
            managed_by: ManagedBy = "manual"
            if labels.get("io.containers.autoupdate") == "registry":
                managed_by = "quadlet"
            elif labels.get("com.docker.compose.project"):
                managed_by = "manual"  # compose not in ManagedBy enum

            # Map container to a valid ServiceKind
            kind: ServiceKind = "application"

            service = LiveService(
                id=name,
                node="srv1",  # podman runs on the host
                kind=kind,
                image=image,
                ports=ports,
                managed_by=managed_by,
                state=state,
            )
            fragment.services.append(service)

        return ProbeResult(
            name=self.name,
            fragment=fragment,
            errors=errors,
            duration_ms=int((datetime.now() - start).total_seconds() * 1000),
        )


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
