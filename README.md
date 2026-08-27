# rw_blueprint

Declarative infrastructure source-of-truth engine.

`rw_blueprint` turns a single canonical YAML model of your infrastructure into
generated artifacts — topology diagrams, documentation, and IaC skeletons — so
that humans, reproducibility tooling, and autonomous agents all read from the
same objective source of truth.

## Why

Infrastructure documentation drifts. Multiple hand-written markdown files
describing the same system inevitably disagree, and agents reasoning against
stale prose faithfully reproduce the drift. `rw_blueprint` inverts the model:
the YAML file is the source of truth, and every diagram, doc, and config is
*derived* from it — never hand-edited, never stale.

## What it does

```
topology.yaml  (canonical, git-versioned, agent-readable)
      |
      +-- validate   (schema check, no dangling references)
      +-- generate   (Mermaid diagrams, markdown docs, quadlet units)
      +-- diff       (compare model against live state -> drift report)
```

## Quick start

```bash
pip install -e ".[dev]"
rw-blueprint validate examples/topology.yaml
rw-blueprint generate examples/topology.yaml --output generated/
```

## Documentation

- [Getting started](docs/getting-started/README.md)
- [Architecture](docs/architecture/README.md)
- [Specifications](docs/specs/)
- [ADRs](docs/adrs/)
- [API reference](docs/api/)
- [Guides](docs/guides/)
- [Research](docs/research/)

## License

[MIT](LICENSE)