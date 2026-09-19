# Operator Guide — Image Lifecycle

**Version:** 0.2.0  
**Date:** 2026-09-19  
**Status:** Production-ready

---

## Overview

The image lifecycle feature provides automated container image management for rw_blueprint deployments. It supports building from source, pulling from registries, and tracking version provenance.

---

## Quick Start

### 1. List Images on Node

```bash
rw-blueprint image list --node infra
```

### 2. Inspect Image Details

```bash
rw-blueprint image inspect honcho:latest --node infra
```

### 3. Pull Image from Registry

```bash
rw-blueprint image pull honcho:latest --registry ghcr.io
```

### 4. Build from Source

```bash
rw-blueprint image build honcho-api \
  --source /home/sysop/honcho \
  --node infra
```

### 5. Push to Registry

```bash
rw-blueprint image push honcho:latest \
  --registry ghcr.io
```

### 6. Prune Old Images

```bash
rw-blueprint image prune --node infra --keep-latest 5
```

---

## Configuration

### Topology YAML

Add `image_config` to any service:

```yaml
services:
  - id: honcho-api
    node: infra
    kind: application
    service_type: container
    image: localhost/honcho:latest
    image_config:
      source: ghcr.io/rapidwebs-Enterprise
      build_context: /home/sysop/honcho
      tag_strategy: git-sha
      labels:
        org.git.sha: "{{ env.GIT_SHA }}"
        org.opencontainers.image.source: "{{ env.GIT_URL }}"
      build_args:
        BUILD_TYPE: production
```

### Tag Strategies

| Strategy | Description | Example |
|----------|-------------|---------|
| `latest` | Always use "latest" tag | `honcho:latest` |
| `git-sha` | Use short git commit SHA | `honcho:a7b3c9d` |
| `semver` | Use semantic version from package.json | `honcho:v2.1.3` |

---

## Security

### Path Traversal Protection

Build contexts are validated against allowed roots:
- `/home/<user>/Workspaces/*`
- `/tmp/*`

Attempting to build from paths like `/etc/shadow` or `/root/.ssh` will be blocked.

### Label Sanitization

Labels are validated with regex `^[a-zA-Z0-9_.\-]+$`. Invalid labels are silently removed.

### Disk Space Check

Before building, the system checks available disk space on the target node. Minimum required: 5GB (configurable).

---

## Deployment Integration

### Dry-Run Mode

Preview what would be deployed without applying:

```bash
rw-blueprint deploy topology.yaml --node infra --dry-run
```

Output shows:
- Services that would be created/updated/deleted
- Configuration paths
- Total action count

### Auto-Rollback

If health checks fail after deployment, rw_blueprint automatically rolls back:

```bash
rw-blueprint deploy topology.yaml --node infra
# If health check fails:
#   ✓ Honcho-API: healthy
#   ✗ Caddy: unhealthy
#   Health check failed for caddy. Rollback requested.
#   ✓ Rolled back caddy
```

Use `--force` to skip auto-rollback:

```bash
rw-blueprint deploy topology.yaml --node infra --force
```

---

## Troubleshooting

### Build Context Not Found

```
Error: Build context does not exist: /path/to/source
```

**Solution:** Ensure the source path exists and is a directory.

### Insufficient Disk Space

```
Error: Insufficient disk space on infra for build
```

**Solution:** Free up space on the target node or increase the threshold.

### Image Pull Failed

```
Error: Failed to pull honcho:latest: unauthorized
```

**Solution:** Configure registry auth in `~/.docker/config.json` or `~/.containers/auth.json`.

### Circular Dependency Detected

```
Error: Circular dependency detected: a -> b -> c -> a
```

**Solution:** Review service dependencies in topology.yaml.

---

## Best Practices

1. **Always use dry-run first** to preview changes
2. **Pin image versions** using git-sha strategy for reproducibility
3. **Tag consistently** across environments (dev/staging/prod)
4. **Monitor disk space** before large builds
5. **Keep deployment history** for audit trails

---

## API Reference

### ImageRef Model

| Field | Type | Description |
|-------|------|-------------|
| `name` | str | Image name (e.g., `honcho`) |
| `tag` | str | Image tag (e.g., `v2.1.3`) |
| `digest` | str \| None | SHA256 digest |
| `source` | str | Origin: `build` or `pull` |
| `built_at` | datetime \| None | Build timestamp |
| `git_sha` | str \| None | Commit SHA (for builds) |
| `git_repo` | str \| None | Git remote URL |
| `labels` | dict[str, str] | Container labels |

### ImageConfig Model

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `source` | str \| None | None | Registry URL |
| `build_context` | str \| None | None | Local path for builds |
| `tag_strategy` | str | `latest` | Tagging strategy |
| `labels` | dict[str, str] | `{}` | Container labels |
| `build_args` | dict[str, str] | `{}` | Build arguments |

---

## Related Documentation

- [SPEC: Image Lifecycle](../specs/image-lifecycle.md)
- [ADR-019: Controller Pattern](../adrs/0019-controller-pattern.md)
- [Synthesis: Image Lifecycle](../synthesis-image-lifecycle.md)

---

**Last Updated:** 2026-09-19
