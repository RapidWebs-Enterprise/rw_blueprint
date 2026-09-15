"""Tests for health verifier."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from rw_blueprint.deployer.verify import HealthVerifier, HealthStatus


class TestHealthVerifier:
    """Test HealthVerifier."""

    def test_verify_service_running(self):
        """Test verifying a running service."""
        manager = MagicMock()
        manager.execute.return_value = MagicMock(
            success=True, returncode=0, stdout="active\n", stderr=""
        )

        verifier = HealthVerifier(manager)
        result = verifier.verify("infra", "caddy")

        assert result.healthy is True
        assert result.checks_passed == 1
        assert result.checks_failed == 0

    def test_verify_service_failed(self):
        """Test verifying a failed service."""
        manager = MagicMock()
        manager.execute.return_value = MagicMock(
            success=False, returncode=1, stdout="", stderr="failed"
        )

        verifier = HealthVerifier(manager)
        result = verifier.verify("infra", "caddy")

        assert result.healthy is False
        assert result.checks_failed == 1

    def test_verify_with_http_check(self):
        """Test health check with HTTP endpoint."""
        manager = MagicMock()
        # First call: systemctl is-active -> active
        # Second call: curl HTTP -> 200
        manager.execute.side_effect = [
            MagicMock(success=True, returncode=0, stdout="active\n", stderr=""),
            MagicMock(success=True, returncode=0, stdout="200\n", stderr=""),
        ]

        verifier = HealthVerifier(manager)
        result = verifier.verify(
            "infra",
            "honcho-api",
            health_check={"http": {"url": "http://localhost:8000/health", "expected_status": 200}},
        )

        assert isinstance(result, HealthStatus)
        assert result.healthy is True
        assert result.checks_passed == 2
        assert result.checks_failed == 0

    def test_verify_http_failure(self):
        """Test health check with failing HTTP endpoint."""
        manager = MagicMock()
        manager.execute.side_effect = [
            MagicMock(success=True, returncode=0, stdout="active\n", stderr=""),
            MagicMock(success=True, returncode=0, stdout="500\n", stderr=""),
        ]

        verifier = HealthVerifier(manager)
        result = verifier.verify(
            "infra",
            "honcho-api",
            health_check={"http": {"url": "http://localhost:8000/health", "expected_status": 200}},
        )

        assert result.healthy is False
        assert result.checks_failed == 1

    def test_verify_timeout(self):
        """Test health check with timeout."""
        manager = MagicMock()
        manager.execute.return_value = MagicMock(
            success=True, returncode=0, stdout="activating\n", stderr=""
        )

        verifier = HealthVerifier(manager)
        result = verifier.verify("infra", "caddy", timeout=1)

        # Should still return a valid status (just not healthy if still activating)
        assert isinstance(result, HealthStatus)


class TestHealthStatus:
    """Test HealthStatus dataclass."""

    def test_healthy_status(self):
        """Test healthy status creation."""
        status = HealthStatus(healthy=True, checks_passed=1, checks_failed=0)
        assert status.healthy is True

    def test_unhealthy_status(self):
        """Test unhealthy status creation."""
        status = HealthStatus(healthy=False, checks_passed=0, checks_failed=1)
        assert status.healthy is False
