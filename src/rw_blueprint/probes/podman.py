"""Podman probe - observes podman containers via ``podman ps --format json``."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Literal

from rw_blueprint.live_state import LivePort, LiveService, LiveStateFragment
from rw_blueprint.probes.base import Probe, ProbeResult
from rw_blueprint.schema import ManagedBy, ServiceKind


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
                node=self.host_node,  # podman runs on the host
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
