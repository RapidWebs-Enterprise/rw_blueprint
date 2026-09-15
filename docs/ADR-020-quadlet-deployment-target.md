# ADR-020: Quadlet as Primary Deployment Target

**Status**: Accepted  
**Date**: 2026-09-15  
**Context**: rw_blueprint generates deployment artifacts; which format should be the primary target?

## 1. Decision

Use **Podman Quadlet** (`.container` files) as the primary deployment target for containerized services on systemd-based Linux hosts.

## 2. Motivations

- Native systemd integration (no daemon required)
- Automatic restart on failure
- Dependency ordering via `Requires=`/`After=`
- Rootless and rootful modes supported
- Part of Podman (already installed on infra)
- Configuration is declarative INI-style

## 3. Consequences

### Positive
- Leverages existing systemd infrastructure
- No additional daemons to manage
- Standard Linux service management tools work
- Easy to debug with `journalctl`, `systemctl`
- Secure by default (rootless mode)

### Negative
- Linux-only (no Windows/macOS)
- Podman-specific (not Docker-compatible)
- Limited to single-host deployment
- No built-in orchestration across nodes

## 4. Generated Unit Example

```ini
[Unit]
Description=Caddy Reverse Proxy
Requires=honcho-api.service
After=honcho-api.service network-online.target

[Container]
Image=localhost/caddy-cloudflare:latest
PublishPort=80:80
PublishPort=443:443
Volume=caddy-data:/data
EnvironmentFile=/etc/caddy/environment

[Service]
Restart=on-failure
TimeoutStartSec=120
```

## 5. Alternatives Considered

### 5.1 Docker Compose
- **Rejected**: Requires Docker daemon, less secure

### 5.2 Kubernetes
- **Rejected**: Overkill for single-node, requires cluster

### 5.3 Raw `podman run` scripts
- **Rejected**: No restart guarantees, manual management

### 5.4 Incus Containers
- **Accepted for**: VM/container nodes (already using on srv1)
- **Not used for**: Application services (Quadlet is simpler)

## 6. Migration Path

Current state: Quadlet files generated but not deployed  
Target state: Controller pushes files and starts services

```bash
# Phase 1: Generate (done)
rw-blueprint generate topology.yaml docs/generated/

# Phase 2: Deploy (next)
rw-blueprint deploy --nodes infra --services caddy honcho-api

# Phase 3: Reconcile (future)
rw-blueprint reconcile --continuous --interval 60s
```

## 7. References

- [Podman Quadlet Documentation](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html)
- [Kuadrat Project](https://github.com/rifkyputra/kuadrat)
- [Systemd Service Management](https://www.freedesktop.org/software/systemd/man/systemd.service.html)
