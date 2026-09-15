"""Health verifier - checks service health after deployment.

Verifies that deployed services are running and healthy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rw_blueprint.deployer.targets import RunResult, TargetManager


@dataclass
class HealthStatus:
    """Health check status for a service."""

    healthy: bool
    checks_passed: int
    checks_failed: int
    details: dict[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.details is None:
            self.details = {}


class HealthVerifier:
    """Verify service health after deployment."""

    def __init__(self, target_manager: TargetManager):
        self.target = target_manager

    def verify(
        self,
        node: str,
        service: str,
        timeout: int = 30,
        health_check: dict[str, Any] | None = None,
    ) -> HealthStatus:
        """Verify service health.

        Args:
            node: Target node identifier.
            service: Service name.
            timeout: Maximum wait time in seconds.
            health_check: Optional health check configuration.

        Returns:
            HealthStatus with check results.
        """
        checks_passed = 0
        checks_failed = 0
        details: dict[str, Any] = {}

        # Check 1: Service is active
        result = self.target.execute(
            node, ["systemctl", "is-active", f"{service}.container"]
        )
        if result.success and result.stdout.strip() == "active":
            checks_passed += 1
            details["systemd"] = "active"
        else:
            checks_failed += 1
            details["systemd"] = result.stderr or "inactive"

        # Check 2: HTTP health endpoint (if configured)
        if health_check and "http" in health_check:
            http_config = health_check["http"]
            url = http_config.get("url")
            expected_status = http_config.get("expected_status", 200)

            if url:
                result = self.target.execute(
                    node,
                    ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", url],
                    timeout=timeout,
                )
                if result.success:
                    actual_status = int(result.stdout.strip())
                    if actual_status == expected_status:
                        checks_passed += 1
                        details["http"] = f"status={actual_status}"
                    else:
                        checks_failed += 1
                        details["http"] = f"expected={expected_status}, got={actual_status}"
                else:
                    checks_failed += 1
                    details["http"] = f"curl failed: {result.stderr}"

        return HealthStatus(
            healthy=checks_failed == 0,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            details=details,
        )
