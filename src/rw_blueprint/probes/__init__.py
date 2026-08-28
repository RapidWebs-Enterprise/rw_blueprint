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

from rw_blueprint.probes.base import Probe, ProbeResult
from rw_blueprint.probes.dns import DnsProbe
from rw_blueprint.probes.incus import IncusProbe
from rw_blueprint.probes.podman import PodmanProbe
from rw_blueprint.probes.port import PortProbe
from rw_blueprint.probes.registry import ProbeRegistry
from rw_blueprint.probes.tailscale import TailscaleProbe

__all__ = [
    "Probe",
    "ProbeResult",
    "IncusProbe",
    "PodmanProbe",
    "PortProbe",
    "DnsProbe",
    "TailscaleProbe",
    "ProbeRegistry",
]
