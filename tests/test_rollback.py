"""Tests for rollback executor."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from rw_blueprint.deployer.rollback import RollbackExecutor, RollbackResult
from rw_blueprint.deployer.state import DeploymentRecord, DeploymentState
from rw_blueprint.deployer.targets import RunResult
from pathlib import Path


class TestRollbackExecutor:
    """Test RollbackExecutor."""

    @patch("rw_blueprint.deployer.targets.run")
    def test_rollback_to_previous(self, mock_run):
        """Test rolling back to previous healthy version."""
        manager = MagicMock()
        manager.execute.return_value = RunResult(success=True, returncode=0, stdout="", stderr="")
        manager.transfer_file.return_value = RunResult(success=True, returncode=0, stdout="", stderr="")

        state = DeploymentState(Path("/tmp/test-state"))
        previous_record = DeploymentRecord(
            version="1.0.0",
            deployed_at="2026-09-15T10:00:00Z",
            deployed_by="sysop",
            status="healthy",
            image="localhost/caddy:old",
            config_hash="sha256:old",
        )
        state.record("infra", "caddy", previous_record)

        executor = RollbackExecutor(manager, state)
        result = executor.rollback("infra", "caddy")

        assert result.success is True

    @patch("rw_blueprint.deployer.targets.run")
    def test_rollback_no_previous(self, mock_run):
        """Test rollback when no previous version exists."""
        manager = MagicMock()
        state = DeploymentState(Path("/tmp/test-state-rollback"))
        # Clear any existing state
        state_file = state._get_state_file("infra", "caddy")
        if state_file.exists():
            state_file.unlink()

        executor = RollbackExecutor(manager, state)
        result = executor.rollback("infra", "caddy")

        assert result.success is False
        assert "No previous healthy version" in result.error_message

    @patch("rw_blueprint.deployer.targets.run")
    def test_rollback_failure(self, mock_run):
        """Test rollback failure."""
        manager = MagicMock()
        manager.execute.return_value = RunResult(success=False, returncode=1, stdout="", stderr="Failed")

        state = DeploymentState(Path("/tmp/test-state"))
        previous_record = DeploymentRecord(
            version="1.0.0",
            deployed_at="2026-09-15T10:00:00Z",
            deployed_by="sysop",
            status="healthy",
            image="localhost/caddy:old",
            config_hash="sha256:old",
        )
        state.record("infra", "caddy", previous_record)

        executor = RollbackExecutor(manager, state)
        result = executor.rollback("infra", "caddy")

        assert result.success is False


class TestRollbackResult:
    """Test RollbackResult dataclass."""

    def test_success_result(self):
        """Test successful rollback result."""
        result = RollbackResult(success=True, service="caddy", node="infra", error_message=None)
        assert result.success is True

    def test_failure_result(self):
        """Test failed rollback result."""
        result = RollbackResult(success=False, service="caddy", node="infra", error_message="Failed")
        assert result.success is False
        assert "Failed" in result.error_message
