"""Tests for dependency graph module."""

from __future__ import annotations

import pytest

from rw_blueprint.deployer.graph import (
    CircularDependencyError,
    build_dependency_graph,
    detect_cycles,
    topological_sort,
)


class TestDependencyGraph:
    """Test dependency graph construction and validation."""

    def test_build_graph_empty(self):
        """Build graph from empty service list."""
        graph = build_dependency_graph([])
        assert len(graph.services) == 0

    def test_build_graph_single_service_no_deps(self):
        """Build graph with single service, no dependencies."""
        services = [
            type('Service', (), {'id': 'caddy', 'depends_on': []})()
        ]
        graph = build_dependency_graph(services)
        assert 'caddy' in graph.services
        assert graph.services['caddy'].depends_on == []

    def test_build_graph_linear_chain(self):
        """Build graph with linear dependency chain."""
        services = [
            type('Service', (), {'id': 'db', 'depends_on': []})(),
            type('Service', (), {'id': 'api', 'depends_on': ['db']})(),
            type('Service', (), {'id': 'caddy', 'depends_on': ['api']})(),
        ]
        graph = build_dependency_graph(services)
        assert graph.services['db'].dependents == ['api']
        assert graph.services['api'].dependents == ['caddy']
        assert graph.services['caddy'].dependents == []

    def test_build_graph_diamond(self):
        """Build graph with diamond dependency pattern."""
        services = [
            type('Service', (), {'id': 'db', 'depends_on': []})(),
            type('Service', (), {'id': 'api1', 'depends_on': ['db']})(),
            type('Service', (), {'id': 'api2', 'depends_on': ['db']})(),
            type('Service', (), {'id': 'proxy', 'depends_on': ['api1', 'api2']})(),
        ]
        graph = build_dependency_graph(services)
        assert set(graph.services['db'].dependents) == {'api1', 'api2'}
        assert graph.services['proxy'].dependents == []


class TestTopologicalSort:
    """Test topological sort algorithm."""

    def test_sort_empty(self):
        """Sort empty graph."""
        graph = build_dependency_graph([])
        layers = topological_sort(graph)
        assert layers == []

    def test_sort_single_service(self):
        """Sort single service."""
        services = [
            type('Service', (), {'id': 'caddy', 'depends_on': []})()
        ]
        graph = build_dependency_graph(services)
        layers = topological_sort(graph)
        assert len(layers) == 1
        assert layers[0] == ['caddy']

    def test_sort_linear_chain(self):
        """Sort linear dependency chain."""
        services = [
            type('Service', (), {'id': 'db', 'depends_on': []})(),
            type('Service', (), {'id': 'api', 'depends_on': ['db']})(),
            type('Service', (), {'id': 'caddy', 'depends_on': ['api']})(),
        ]
        graph = build_dependency_graph(services)
        layers = topological_sort(graph)
        # Should be 3 layers
        assert len(layers) == 3
        # Order should be db -> api -> caddy
        flat = [s for layer in layers for s in layer]
        assert flat.index('db') < flat.index('api')
        assert flat.index('api') < flat.index('caddy')

    def test_sort_parallel_branches(self):
        """Sort with parallel branches."""
        services = [
            type('Service', (), {'id': 'db', 'depends_on': []})(),
            type('Service', (), {'id': 'cache', 'depends_on': []})(),
            type('Service', (), {'id': 'api', 'depends_on': ['db', 'cache']})(),
        ]
        graph = build_dependency_graph(services)
        layers = topological_sort(graph)
        # db and cache should be in first layer (parallel)
        assert len(layers[0]) == 2
        assert set(layers[0]) == {'db', 'cache'}
        # api should be in second layer
        assert layers[1] == ['api']

    def test_sort_diamond(self):
        """Sort diamond dependency pattern."""
        services = [
            type('Service', (), {'id': 'db', 'depends_on': []})(),
            type('Service', (), {'id': 'api1', 'depends_on': ['db']})(),
            type('Service', (), {'id': 'api2', 'depends_on': ['db']})(),
            type('Service', (), {'id': 'proxy', 'depends_on': ['api1', 'api2']})(),
        ]
        graph = build_dependency_graph(services)
        layers = topological_sort(graph)
        # db first, then api1/api2, then proxy
        assert len(layers) == 3
        assert layers[0] == ['db']
        assert set(layers[1]) == {'api1', 'api2'}
        assert layers[2] == ['proxy']

    def test_detect_cycle(self):
        """Detect circular dependency."""
        services = [
            type('Service', (), {'id': 'a', 'depends_on': ['b']})(),
            type('Service', (), {'id': 'b', 'depends_on': ['a']})(),
        ]
        graph = build_dependency_graph(services)
        cycles = detect_cycles(graph)
        assert len(cycles) > 0

    def test_no_cycle(self):
        """No cycle in valid DAG."""
        services = [
            type('Service', (), {'id': 'db', 'depends_on': []})(),
            type('Service', (), {'id': 'api', 'depends_on': ['db']})(),
        ]
        graph = build_dependency_graph(services)
        cycles = detect_cycles(graph)
        assert len(cycles) == 0

    def test_self_cycle(self):
        """Detect self-dependency as cycle."""
        services = [
            type('Service', (), {'id': 'a', 'depends_on': ['a']})(),
        ]
        graph = build_dependency_graph(services)
        cycles = detect_cycles(graph)
        assert len(cycles) > 0


class TestDependencyError:
    """Test error handling."""

    def test_circular_dependency_raises(self):
        """Topological sort should raise on circular dependency."""
        services = [
            type('Service', (), {'id': 'a', 'depends_on': ['b']})(),
            type('Service', (), {'id': 'b', 'depends_on': ['a']})(),
        ]
        graph = build_dependency_graph(services)
        with pytest.raises(CircularDependencyError):
            topological_sort(graph)
