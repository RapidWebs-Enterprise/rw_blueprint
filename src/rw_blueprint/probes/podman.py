"""Podman probe - observes podman containers via ``podman ps --format json``.

Supports both local and remote (SSH) execution.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Literal

from rw_blueprint.live_state import LivePort, LiveService, LiveStateFragment
from rw_blueprint.probes.base import Probe, ProbeResult
from rw_blueprint.probes.ssh import run_local_cmd, run_remote_cmd
from rw_blueprint.schema import ManagedBy, ServiceKind

_logger = logging.getLogger(__name__)


class PodmanProbe(Probe):
    """Probe podman containers via ``podman ps --format json``."""

    @property
    def name(self) -> str:
        return "podman"

    def run(self) -> ProbeResult:
        start = datetime.now()
        errors: list[str] = []
        fragment = LiveStateFragment()

        # Try local first, then SSH
        exit_code, stdout, stderr = run_local_cmd(["podman", "ps", "--all", "--format", "json"])

        if exit_code != 0:
            # Fall back to remote SSH
            _logger.info("Local podman failed, trying SSH to %s", self.host_node)
            exit_code, stdout, stderr = run_remote_cmd(
                self.host_node,
                ["podman", "ps", "--all", "--format", "json"],
                timeout=self.timeout,
            )

        # If still empty or failed, try with sudo (for rootful containers on remote hosts)
        if exit_code == 0 and stdout and stdout.strip() == "[]":
            exit_code2, stdout2, stderr2 = run_remote_cmd(
                self.host_node,
                ["sudo", "podman", "ps", "--all", "--format", "json"],
                timeout=self.timeout,
            )
            if exit_code2 == 0 and stdout2:
                stdout = stdout2
                stderr = stderr2
                exit_code = exit_code2

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
            for p in c.get("Ports") or []:
                if p.get("PublicPort"):
                    ports.append(
                        LivePort(
                            port=p["PrivatePort"],
                            public=p["PublicPort"],
                            protocol=p.get("Type", "tcp").lower(),
                        )
                    )

            # Determine managed_by from labels
            labels = c.get("Labels") or {}
            managed_by: ManagedBy = "manual"
            if labels.get("io.containers.autoupdate") == "registry":
                managed_by = "quadlet"
            elif labels.get("com.docker.compose.project"):
                managed_by = "manual"  # compose not in ManagedBy enum

            # Map container to a valid ServiceKind
            kind: ServiceKind = "application"

            service = LiveService(
                id=name,
                node=self.host_node,
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
