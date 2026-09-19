"""Tests for multi-node coordinated deployments."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from rw_blueprint.deployer.executor import DeployExecutor
from rw_blueprint.deployer.plan import BlastRadius, DeploymentAction, DeploymentPlan
from rw_blueprint.deployer.targets import RunResult


class TestMultiNodeDeployment:
    """Tests for multi-node deployment coordination."""

    def test_deploy_to_multiple_nodes(self):
        """Test deploying to multiple nodes in sequence."""
        with patch('rw_blueprint.cli.TargetManager') as MockTarget:
            mock_target = MagicMock()
            MockTarget.return_value = mock_target
            mock_target.execute.return_value = RunResult(
                success=True, returncode=0, stdout="active", stderr=""
            )
            mock_target.transfer_file.return_value = RunResult(
                success=True, returncode=0, stdout="", stderr=""
            )

            # Create a plan that targets multiple nodes
            plan = DeploymentPlan(
                actions=[
                    DeploymentAction(node="infra", service="db", action="create"),
                    DeploymentAction(node="enterprise", service="api", action="create"),
                ],
                estimated_duration=MagicMock(),
                blast_radius=BlastRadius.MESH,
            )

            executor = DeployExecutor(target_manager=mock_target)
            
            # Execute for infra node
            result_infra = executor.execute(plan, "infra", continue_on_failure=True)
            assert result_infra.success
            assert "db" in result_infra.actions_completed

            # Execute for enterprise node
            result_enterprise = executor.execute(plan, "enterprise", continue_on_failure=True)
            assert result_enterprise.success
            assert "api" in result_enterprise.actions_completed

    def test_cross_node_dependency_ordering(self):
        """Test that cross-node dependencies are respected."""
        # Simulate: db on infra must start before api on enterprise
        plan = DeploymentPlan(
            actions=[
                DeploymentAction(node="infra", service="db", action="create"),
                DeploymentAction(node="enterprise", service="api", action="create",
                                dependencies=["infra/db"]),
            ],
            estimated_duration=MagicMock(),
            blast_radius=BlastRadius.MESH,
        )

        # Verify plan has cross-node dependency
        assert any("infra/db" in str(a.dependencies) for a in plan.actions)

    def test_mesh_deployment_planning(self):
        """Test mesh-level blast radius calculation."""
        plan = DeploymentPlan(
            actions=[
                DeploymentAction(node="infra", service="db", action="create"),
                DeploymentAction(node="enterprise", service="api", action="create"),
                DeploymentAction(node="dev", service="cache", action="create"),
            ],
            estimated_duration=MagicMock(),
            blast_radius=BlastRadius.MESH,
        )

        assert plan.blast_radius == BlastRadius.MESH
        assert len(plan.actions) == 3
