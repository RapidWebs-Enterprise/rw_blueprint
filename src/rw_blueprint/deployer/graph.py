"""Dependency graph for service orchestration.

Provides topological sorting and cycle detection for service deployment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class ServiceLike(Protocol):
    """Protocol for service objects with id and depends_on."""

    id: str
    depends_on: list[str]


@dataclass
class ServiceNode:
    """Node in the dependency graph."""

    id: str
    depends_on: list[str] = field(default_factory=list)
    dependents: list[str] = field(default_factory=list)


@dataclass
class DependencyGraph:
    """Directed acyclic graph (DAG) of service dependencies."""

    services: dict[str, ServiceNode] = field(default_factory=dict)


class CircularDependencyError(Exception):
    """Raised when a circular dependency is detected."""

    pass


def build_dependency_graph(services: list[ServiceLike]) -> DependencyGraph:
    """Build dependency graph from service list.

    Args:
        services: List of services with id and depends_on fields.

    Returns:
        DependencyGraph with all services and their relationships.
    """
    graph = DependencyGraph()

    # Create nodes
    for service in services:
        graph.services[service.id] = ServiceNode(
            id=service.id,
            depends_on=list(service.depends_on),
        )

    # Build reverse relationships (dependents)
    for service in services:
        for dep_id in service.depends_on:
            if dep_id in graph.services:
                graph.services[dep_id].dependents.append(service.id)

    return graph


def detect_cycles(graph: DependencyGraph) -> list[list[str]]:
    """Detect circular dependencies using DFS.

    Args:
        graph: Dependency graph to check.

    Returns:
        List of cycles found (each cycle is a list of service ids).
    """
    cycles: list[list[str]] = []
    visited: set[str] = set()
    rec_stack: set[str] = set()
    path: list[str] = []

    def dfs(node_id: str) -> None:
        visited.add(node_id)
        rec_stack.add(node_id)
        path.append(node_id)

        for dependent in graph.services[node_id].dependents:
            if dependent not in visited:
                dfs(dependent)
            elif dependent in rec_stack:
                # Found a cycle
                cycle_start = path.index(dependent)
                cycles.append(path[cycle_start:] + [dependent])

        path.pop()
        rec_stack.remove(node_id)

    for service_id in graph.services:
        if service_id not in visited:
            dfs(service_id)

    return cycles


def topological_sort(graph: DependencyGraph) -> list[list[str]]:
    """Sort services into startup layers using topological sort.

    Uses Kahn's algorithm to produce layers where each layer can start
    in parallel (all dependencies satisfied).

    Args:
        graph: Dependency graph.

    Returns:
        List of layers, where each layer is a list of service ids that
        can start in parallel.

    Raises:
        CircularDependencyError: If a cycle is detected.
    """
    # Calculate in-degrees
    in_degree: dict[str, int] = {
        sid: len(node.depends_on)
        for sid, node in graph.services.items()
    }

    # Start with services that have no dependencies
    queue: list[str] = [
        sid for sid, deg in in_degree.items() if deg == 0
    ]
    layers: list[list[str]] = []

    while queue:
        # Current layer: all services with in-degree 0
        layer = queue.copy()
        queue = []
        layers.append(layer)  # Append layer once, not per service

        # Reduce in-degree for dependents
        for service_id in layer:
            for dependent in graph.services[service_id].dependents:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

    # Check for cycles
    if len([s for layer in layers for s in layer]) != len(graph.services):
        cycles = detect_cycles(graph)
        cycle_strs = [" -> ".join(c) for c in cycles[:3]]  # Limit output
        raise CircularDependencyError(
            f"Circular dependency detected: {', '.join(cycle_strs)}"
        )

    return layers
