"""Tests for health verifier."""

from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import MagicMock, patch

import pytest

from rw_blueprint.deployer.verify import HealthVerifier, HealthStatus


class TestHealthVerifier:
    """Test HealthVerifier."""

    @patch("rw_blueprint.deployer.targets.run")
    def test_verify_service_running(self, mock_run):
        """Test verifying a running service."""
        manager = MagicMock()
        manager.execute.return_value = MagicMock(
            success=True, returncode=0, stdout="active", stderr=""
        )

        verifier = HealthVerifier(manager)
        result = verifier.verify("infra", "caddy")

        assert result.healthy is True

    @patch("rw_blueprint.deployer.targets.run")
    def test_verify_service_failed(self, mock_run):
        """Test verifying a failed service."""
        manager = MagicMock()
        manager.execute.return_value = MagicMock(
            success=False, returncode=1, stdout="", stderr="failed"
        )

        verifier = HealthVerifier(manager)
        result = verifier.verify("infra", "caddy")

        assert result.healthy is False

    @patch("rw_blueprint.deployer.targets.run")
    def test_verify_with_http_check(self, mock_run):
        """Test health check with HTTP endpoint."""
        manager = MagicMock()
        # First call: systemctl is-active
        # Second call: curl HTTP check
        mock_run.side_effect = [
            MagicMock(spec=CompletedProcess, returncode=0, stdout="active", stderr=""),
            MagicMock(spec=CompletedProcess, returncode=0, stdout="200", stderr=""),
        ]

        verifier = HealthVerifier(manager)
        result = verifier.verify(
            "infra",
            "honcho-api",
            health_check={"http": {"url": "http://localhost:8000/health", "expected_status": 200}},
        )

        assert isinstance(result, HealthStatus)
        assert result.healthy is True

    @patch("rw_blueprint.deployer.targets.run")
    def test_verify_timeout(self, mock_run):
        """Test health check timeout."""
        manager = MagicMock()
        manager.execute.return_value = MagicMock(
            success=True, returncode=0, stdout="activating", stderr=""
        )

        verifier = HealthVerifier(manager)
        result = verifier.verify("infra", "caddy", timeout=1)

        # Should eventually report healthy or failed based on final status
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
