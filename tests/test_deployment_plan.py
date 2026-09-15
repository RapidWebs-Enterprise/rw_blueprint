"""Tests for deployment plan generator."""

from __future__ import annotations

from datetime import timedelta

import pytest

from rw_blueprint.deployer.plan import (
    BlastRadius,
    DeploymentAction,
    DeploymentPlan,
    PlanGenerator,
)


class MockService:
    """Mock service for testing."""

    def __init__(self, id: str, node: str, kind: str = "application"):
        self.id = id
        self.node = node
        self.kind = kind
        self.service_type = "container"
        self.privileged = False
        self.image = f"localhost/{id}:latest"
        self.ports = []
        self.depends_on = []


class TestDeploymentPlan:
    """Test DeploymentPlan dataclass."""

    def test_create_plan(self):
        """Create a deployment plan."""
        plan = DeploymentPlan(
            actions=[DeploymentAction(node="infra", service="caddy", action="create")],
            estimated_duration=timedelta(seconds=30),
            blast_radius=BlastRadius.NODE,
            requires_approval=False,
        )
        assert len(plan.actions) == 1
        assert plan.actions[0].service == "caddy"

    def test_empty_plan(self):
        """Create empty plan."""
        plan = DeploymentPlan(actions=[], estimated_duration=timedelta(0), blast_radius=BlastRadius.NODE, requires_approval=False)
        assert len(plan.actions) == 0


class TestPlanGenerator:
    """Test PlanGenerator."""

    def test_generate_no_changes(self):
        """Generate plan with no changes needed."""
        generator = PlanGenerator()
        services = [MockService("caddy", "infra")]
        existing = {"caddy": MockService("caddy", "infra")}
        plan = generator.generate(services, existing)
        assert len(plan.actions) == 0

    def test_generate_new_service(self):
        """Generate plan to create new service."""
        generator = PlanGenerator()
        services = [MockService("caddy", "infra")]
        existing = {}
        plan = generator.generate(services, existing)
        assert len(plan.actions) == 1
        assert plan.actions[0].action == "create"
        assert plan.actions[0].service == "caddy"

    def test_generate_update_service(self):
        """Generate plan to update existing service."""
        generator = PlanGenerator()
        old_service = MockService("caddy", "infra")
        old_service.image = "localhost/caddy:old"
        new_service = MockService("caddy", "infra")
        new_service.image = "localhost/caddy:new"

        plan = generator.generate([new_service], {"caddy": old_service})
        assert len(plan.actions) == 1
        assert plan.actions[0].action == "update"

    def test_generate_delete_service(self):
        """Generate plan to delete service."""
        generator = PlanGenerator()
        services = []
        existing = {"caddy": MockService("caddy", "infra")}
        plan = generator.generate(services, existing)
        assert len(plan.actions) == 1
        assert plan.actions[0].action == "delete"

    def test_generate_multiple_services(self):
        """Generate plan for multiple services."""
        generator = PlanGenerator()
        services = [
            MockService("db", "infra"),
            MockService("api", "infra"),
            MockService("caddy", "infra"),
        ]
        existing = {}
        plan = generator.generate(services, existing)
        assert len(plan.actions) == 3
        assert all(a.action == "create" for a in plan.actions)
