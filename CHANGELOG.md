# CHANGELOG

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Image lifecycle management (build, pull, push, inspect, prune)
- Dry-run deployment mode (`--dry-run`)
- Auto-rollback on health check failure
- Multi-node coordinated deployment support
- Artifact preservation for rollback
- Partial failure handling (`continue_on_failure`)

### Changed
- Deployment executor now accepts state_tracker parameter
- Rollback uses stored artifacts when available
- Dependency graph supports cross-node relationships

### Fixed
- Build context path traversal validation
- Label sanitization for container images
- Test expectations for partial failure scenarios

## [0.2.0] - 2026-09-14

### Added
- Declarative YAML topology engine
- Multi-node probe system (incus, podman, port, dns, tailscale)
- Drift detection with three-way classification
- MCP server integration
- Quadlet and Incus profile generation
- Topology validation against Pydantic schema
- Documentation generation from topology

### Changed
- Migrated from monolithic script to modular package
- Improved error handling and reporting

### Removed
- Legacy probe implementations

## [0.1.0] - 2026-08-27

### Added
- Initial topology YAML parser
- Basic validation logic
- Single-node probe capability
- Drift report generation

---

## Version History

| Version | Date | Notes |
|---------|------|-------|
| 0.2.0 | 2026-09-14 | Deployment engine, image lifecycle, multi-node probes |
| 0.1.0 | 2026-08-27 | Initial release, basic topology engine |
