# Examples Directory

This directory contains example topology files for rw_blueprint.

## Available Examples

| Example | Description | Use Case |
|---------|-------------|----------|
| [basic-topology.yaml](basic-topology.yaml) | Minimal single-node deployment | Learning basics |
| [advanced-topology.yaml](advanced-topology.yaml) | Multi-node with dependencies | Production patterns |
| [minimal-topology.yaml](minimal-topology.yaml) | Bare-bones required fields | Schema reference |
| [RapidWebs RWDN](../../topology.yaml) | Full production topology | Real-world example |

## Quick Start

```bash
# Validate an example
rw-blueprint validate examples/basic-topology.yaml

# Generate artifacts
rw-blueprint generate examples/basic-topology.yaml --output /tmp/generated/

# Preview deployment
rw-blueprint deploy examples/basic-topology.yaml --node localhost --dry-run
```

## Creating Your Own Topology

1. Copy an example as a starting point
2. Update `metadata.name` and `metadata.updated`
3. Define your zones, nodes, and services
4. Add dependencies and links as needed
5. Validate: `rw-blueprint validate your-topology.yaml`
6. Generate: `rw-blueprint generate your-topology.yaml`

## Best Practices

- Always start with validation before deployment
- Use dependency ordering for service startup
- Define health checks for critical services
- Keep image tags specific (avoid `latest` in production)
- Document custom configurations in comments
