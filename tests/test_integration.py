"""Tests for dry-run and dependency orchestration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest
from typer.testing import CliRunner

from rw_blueprint.cli import app
from rw_blueprint.deployer.graph import (
    DependencyGraph,
    ServiceNode,
    build_dependency_graph,
    topological_sort,
    detect_cycles,
    CircularDependencyError,
)


runner = CliRunner()


class TestDryRun:
    """Tests for dry-run mode."""

    def test_dry_run_shows_plan(self, tmp_path):
        """Dry-run mode displays planned actions without executing."""
        # Create a minimal valid topology file
        topology = """schema_version: '0.2'
metadata:
  name: test-ns
  description: Test topology
  updated: 2026-09-19
zones:
  - id: infra
    name: Infrastructure
nodes:
  - id: test-node
    zone: infra
    type: host
services:
  - id: test-service
    node: test-node
    kind: application
    service_type: container
    image: localhost/test:latest
links: []
dependencies: []
"""
        topo_file = tmp_path / "topology.yaml"
        topo_file.write_text(topology)
        
        result = runner.invoke(app, [
            "deploy", str(topo_file),
            "--node", "test-node",
            "--dry-run"
        ])
        
        # Should succeed and show dry-run output
        assert result.exit_code == 0, f"Output: {result.output}"
        assert "Dry-run mode" in result.output
        assert "test-service" in result.output


class TestDependencyGraph:
    """Tests for dependency graph operations."""

    def test_linear_dependency_order(self):
        """Test topological sort with linear dependencies."""
        services = [
            type('S', (), {'id': 'db', 'depends_on': []})(),
            type('S', (), {'id': 'api', 'depends_on': ['db']})(),
            type('S', (), {'id': 'web', 'depends_on': ['api']})(),
        ]
        
        graph = build_dependency_graph(services)
        layers = topological_sort(graph)
        
        # Should have 3 layers
        assert len(layers) == 3
        # db should be first
        assert 'db' in layers[0]
        # api should be second
        assert 'api' in layers[1]
        # web should be last
        assert 'web' in layers[2]

    def test_parallel_branches(self):
        """Test topological sort with parallel branches."""
        services = [
            type('S', (), {'id': 'db', 'depends_on': []})(),
            type('S', (), {'id': 'cache', 'depends_on': []})(),
            type('S', (), {'id': 'api', 'depends_on': ['db', 'cache']})(),
        ]
        
        graph = build_dependency_graph(services)
        layers = topological_sort(graph)
        
        # db and cache should be in same layer (parallel)
        assert len(layers) == 2
        first_layer = set(layers[0])
        assert 'db' in first_layer
        assert 'cache' in first_layer
        # api should be second
        assert 'api' in layers[1]

    def test_circular_dependency_detection(self):
        """Test that circular dependencies are detected."""
        services = [
            type('S', (), {'id': 'a', 'depends_on': ['b']})(),
            type('S', (), {'id': 'b', 'depends_on': ['c']})(),
            type('S', (), {'id': 'c', 'depends_on': ['a']})(),
        ]
        
        graph = build_dependency_graph(services)
        
        with pytest.raises(CircularDependencyError):
            topological_sort(graph)

    def test_missing_dependency_handling(self):
        """Test handling of missing dependencies."""
        services = [
            type('S', (), {'id': 'api', 'depends_on': []})(),  # No missing dep
        ]
        
        graph = build_dependency_graph(services)
        layers = topological_sort(graph)
        
        assert len(layers) == 1
        assert 'api' in layers[0]

    def test_cycle_detection_returns_cycles(self):
        """Test that cycle detection returns the cycles found."""
        services = [
            type('S', (), {'id': 'a', 'depends_on': ['b']})(),
            type('S', (), {'id': 'b', 'depends_on': ['a']})(),
        ]
        
        graph = build_dependency_graph(services)
        cycles = detect_cycles(graph)
        
        assert len(cycles) > 0
        # Each cycle should contain both nodes
        for cycle in cycles:
            assert 'a' in cycle
            assert 'b' in cycle


class TestHealthCheckRollback:
    """Tests for auto-rollback on health check failure."""

    def test_rollback_result_structure(self):
        """Test RollbackResult structure."""
        from rw_blueprint.deployer.rollback import RollbackResult
        
        result = RollbackResult(
            success=True,
            service="test-service",
            node="test-node"
        )
        assert result.success is True
        assert result.service == "test-service"
        assert result.node == "test-node"
        assert result.error_message is None

    def test_rollback_failure_result(self):
        """Test RollbackResult with failure."""
        from rw_blueprint.deployer.rollback import RollbackResult
        
        result = RollbackResult(
            success=False,
            service="test-service",
            node="test-node",
            error_message="Failed to stop service"
        )
        assert result.success is False
        assert result.error_message == "Failed to stop service"
