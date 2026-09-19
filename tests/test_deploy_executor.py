"""Tests for deploy executor."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from rw_blueprint.deployer.executor import DeployExecutor, DeploymentResult
from rw_blueprint.deployer.plan import BlastRadius, DeploymentAction, DeploymentPlan
from rw_blueprint.deployer.targets import RunResult


class TestDeployExecutor:
    """Test DeployExecutor."""

    @patch("rw_blueprint.deployer.targets.run")
    def test_execute_create_service(self, mock_run):
        """Test deploying a new service."""
        mock_run.return_value = MagicMock(
            spec=MagicMock, returncode=0, stdout="", stderr=""
        )

        manager = MagicMock()
        manager.execute.return_value = RunResult(success=True, returncode=0, stdout="", stderr="")
        manager.transfer_file.return_value = RunResult(success=True, returncode=0, stdout="", stderr="")

        executor = DeployExecutor(manager)
        plan = DeploymentPlan(
            actions=[DeploymentAction(node="infra", service="caddy", action="create")],
            estimated_duration=MagicMock(),
            blast_radius=BlastRadius.SERVICE,
        )

        result = executor.execute(plan, "infra")
        assert result.success is True

    @patch("rw_blueprint.deployer.targets.run")
    def test_execute_service_failure(self, mock_run):
        """Test deployment failure with continue_on_failure=False raises."""
        manager = MagicMock()
        manager.execute.return_value = RunResult(
            success=False, returncode=1, stdout="", stderr="Failed to start"
        )

        executor = DeployExecutor(manager)
        plan = DeploymentPlan(
            actions=[DeploymentAction(node="infra", service="caddy", action="create")],
            estimated_duration=MagicMock(),
            blast_radius=BlastRadius.SERVICE,
        )

        with pytest.raises(RuntimeError, match="caddy"):
            executor.execute(plan, "infra", continue_on_failure=False)

    @patch("rw_blueprint.deployer.targets.run")
    def test_execute_partial_failure_continues(self, mock_run):
        """Test partial failure with continue_on_failure=True continues."""
        manager = MagicMock()
        # First call (is-active) succeeds, second (start) fails for caddy
        # Third call (is-active) succeeds, fourth (start) succeeds for honcho-api
        manager.execute.side_effect = [
            RunResult(success=True, returncode=0, stdout="inactive", stderr=""),  # is-active caddy
            RunResult(success=True, returncode=0, stdout="", stderr=""),  # daemon-reload
            RunResult(success=False, returncode=1, stdout="", stderr="Failed to start"),  # start caddy
            RunResult(success=True, returncode=0, stdout="inactive", stderr=""),  # is-active honcho-api
            RunResult(success=True, returncode=0, stdout="", stderr=""),  # daemon-reload
            RunResult(success=True, returncode=0, stdout="active", stderr=""),  # start honcho-api
        ]
        manager.transfer_file.return_value = RunResult(success=True, returncode=0, stdout="", stderr="")

        executor = DeployExecutor(manager)
        plan = DeploymentPlan(
            actions=[
                DeploymentAction(node="infra", service="caddy", action="create"),
                DeploymentAction(node="infra", service="honcho-api", action="create"),
            ],
            estimated_duration=MagicMock(),
            blast_radius=BlastRadius.NODE,
        )

        result = executor.execute(plan, "infra", continue_on_failure=True)

        # Should have partial success
        assert not result.success
        assert "caddy" in result.error_message
        assert "honcho-api" in result.actions_completed

    @patch("rw_blueprint.deployer.targets.run")
    def test_execute_multiple_actions(self, mock_run):
        """Test deploying multiple services."""
        manager = MagicMock()
        manager.execute.return_value = RunResult(success=True, returncode=0, stdout="", stderr="")
        manager.transfer_file.return_value = RunResult(success=True, returncode=0, stdout="", stderr="")

        executor = DeployExecutor(manager)
        plan = DeploymentPlan(
            actions=[
                DeploymentAction(node="infra", service="db", action="create"),
                DeploymentAction(node="infra", service="api", action="create"),
            ],
            estimated_duration=MagicMock(),
            blast_radius=BlastRadius.NODE,
        )

        result = executor.execute(plan, "infra")
        assert result.success is True
        assert len(result.actions_completed) == 2


class TestDeploymentResult:
    """Test DeploymentResult dataclass."""

    def test_success_result(self):
        """Test successful deployment result."""
        result = DeploymentResult(
            success=True,
            node="infra",
            actions_completed=["caddy"],
            error_message=None,
        )
        assert result.success is True

    def test_failure_result(self):
        """Test failed deployment result."""
        result = DeploymentResult(
            success=False,
            node="infra",
            actions_completed=[],
            error_message="Something failed",
        )
        assert result.success is False
        assert "Something failed" in result.error_message
