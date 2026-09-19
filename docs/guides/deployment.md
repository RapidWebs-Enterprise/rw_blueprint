# Deployment Guide

**Version:** 0.2.0  
**Last Updated:** 2026-09-19  
**Target:** Production deployment to RapidWebs Distributed Network (RWDN)

---

## Overview

This guide covers deploying infrastructure services using rw_blueprint. The deployment system supports:

- **Single-node deployment** — Deploy to one target at a time
- **Multi-node deployment** — Coordinate across multiple nodes
- **Dependency ordering** — Services start in correct order
- **Health verification** — Automatic health checks post-deploy
- **Auto-rollback** — Revert on health check failure
- **Dry-run mode** — Preview changes before applying

---

## Prerequisites

### Required Tools

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | Runtime |
| uv | 0.12+ | Package management |
| SSH | OpenSSH 8+ | Remote execution |
| Podman | 4.0+ | Container runtime (on targets) |
| systemd | 250+ | Service management (on targets) |

### Required Access

| Target | SSH User | Tailscale IP | Notes |
|--------|----------|--------------|-------|
| srv1 | sysop | 100.64.94.58 | Hetzner host |
| infra | sysop | 100.79.58.118 | Incus container |
| enterprise | sysop | 100.65.82.48 | Incus container |
| dev | sysop | 100.127.203.36 | Incus container |

### SSH Key Setup

```bash
# Generate key if needed
ssh-keygen -t ed25519 -C "sysop@workstation" -f ~/.ssh/id_ed25519

# Distribute to targets
for node in srv1 infra enterprise dev; do
    ssh-copy-id -i ~/.ssh/id_ed25519.pub sysop@$node
done

# Test connectivity
for node in srv1 infra enterprise dev; do
    ssh sysop@$node "echo OK && hostname"
done
```

---

## Deployment Workflow

### Step 1: Validate Topology

```bash
# Basic validation
rw-blueprint validate topology.yaml

# Validate with custom output
rw-blueprint validate topology.yaml --output /tmp/validated.json

# Expected output:
# Valid topology 'rapidwebs-rwdn' (7 nodes, 11 services).
```

**Common validation errors:**
- Unknown zone reference → Check `zones:` section
- Duplicate ID → Ensure all IDs are unique
- Missing required field → Check service `kind`, `node`, `image`

### Step 2: Generate Artifacts

```bash
# Generate all artifacts
rw-blueprint generate topology.yaml --output docs/generated/

# Expected structure:
# docs/generated/
# ├── quadlet/           # Container units
# │   ├── pgvector.container
# │   ├── honcho-api.container
# │   └── ...
# ├── diagrams/          # Mermaid visualizations
# └── docs/              # Markdown documentation
```

**Verify generation:**
```bash
ls -la docs/generated/quadlet/
# Should show .container files for each service
```

### Step 3: Preview Deployment (Dry-Run)

```bash
# Preview what will be deployed
rw-blueprint deploy topology.yaml --node infra --dry-run

# Expected output:
# Dry-run mode: showing planned changes for infra
#
# Service       Action  Config Path
# pgvector      create  /etc/containers/systemd/pgvector.container
# honcho-api    create  /etc/containers/systemd/honcho-api.container
# ...
#
# Total actions: 5
```

### Step 4: Deploy Services

#### Single Node Deployment

```bash
# Deploy all services on a node
rw-blueprint deploy topology.yaml --node infra

# Deploy specific services only
rw-blueprint deploy topology.yaml --node infra --services pgvector,honcho-api

# Force deploy (skip confirmation + auto-rollback)
rw-blueprint deploy topology.yaml --node infra --force
```

#### Multi-Node Deployment

```bash
# Deploy to multiple nodes sequentially
for node in infra enterprise dev; do
    rw-blueprint deploy topology.yaml --node $node
done
```

#### With Image Lifecycle

```bash
# Build and deploy with image management
rw-blueprint image build honcho-api --source /home/sysop/honcho --node infra
rw-blueprint deploy topology.yaml --node infra --services honcho-api
```

### Step 5: Verify Deployment

```bash
# Check service status
ssh sysop@infra "systemctl status pgvector.service"
ssh sysop@infra "systemctl status honcho-api.service"

# Check container health
ssh sysop@infra "podman ps | grep -E 'pgvector|honcho'"

# Test endpoints
curl http://localhost:5432  # PostgreSQL
curl http://localhost:8000/health  # Honcho API
curl http://localhost:8300/health  # Inference Engine
```

---

## Deployment Strategies

### Strategy 1: Sequential (Default)

Services deploy in dependency order. Waits for each service to be healthy before starting the next.

```
Order: pgvector → rw-inference-engine → honcho-api → agentgateway → caddy
```

**Use when:** Services have strict startup dependencies.

### Strategy 2: Parallel (All at Once)

Deploy all services simultaneously. Faster but riskier.

```bash
# Deploy all services without waiting
rw-blueprint deploy topology.yaml --node infra --parallel
```

**Use when:** Services are independent or you want faster deployment.

### Strategy 3: Rolling (One at a Time)

Deploy one service, verify, then move to next. Safest approach.

```bash
# Manual rolling deployment
for service in pgvector rw-inference-engine honcho-api agentgateway caddy; do
    rw-blueprint deploy topology.yaml --node infra --services $service
    echo "Verifying $service..."
    sleep 10
done
```

**Use when:** Deploying to production with zero-downtime requirements.

---

## Deployment Configuration

### User Config (`~/.rw_blueprint/config.yaml`)

```yaml
ssh:
  default_user: sysop
  key_path: ~/.ssh/id_ed25519
  timeout: 30
  max_concurrent: 5

probes:
  timeout: 30
  retry_count: 3
  parallel: true

deploy:
  continue_on_failure: true
  auto_rollback: true
  health_check_timeout: 60
  confirmation_required: true

images:
  build_timeout: 1800
  max_retries: 3
  registry: docker.io
```

### Environment Variables

```bash
# Override config values
export RW_BLUEPRINT_SSH_TIMEOUT=60
export RW_BLUEPRINT_DEPLOY_AUTO_ROLLBACK=false
export RW_BLUEPRINT_PROBES_PARALLEL=true
```

---

## Deployment Examples

### Example 1: Initial Infrastructure Setup

```bash
# 1. Validate
rw-blueprint validate topology.yaml

# 2. Generate
rw-blueprint generate topology.yaml --output docs/generated/

# 3. Deploy database first (dependency root)
rw-blueprint deploy topology.yaml --node infra --services pgvector

# 4. Verify database
ssh sysop@infra "psql -U honcho -h localhost -c 'SELECT 1'"

# 5. Deploy inference engine
rw-blueprint deploy topology.yaml --node infra --services rw-inference-engine

# 6. Deploy API
rw-blueprint deploy topology.yaml --node infra --services honcho-api

# 7. Deploy proxy
rw-blueprint deploy topology.yaml --node infra --services caddy
```

### Example 2: Service Update

```bash
# 1. Update topology.yaml with new image version
#    Change: image: localhost/honcho:latest
#    To:     image: localhost/honcho:v2.1.0

# 2. Preview changes
rw-blueprint deploy topology.yaml --node infra --dry-run

# 3. Deploy with rollback on failure
rw-blueprint deploy topology.yaml --node infra --services honcho-api

# 4. If health check fails, automatic rollback occurs
```

### Example 3: Full Cluster Deployment

```bash
#!/bin/bash
# deploy-all.sh

NODES="infra enterprise dev"

for node in $NODES; do
    echo "=== Deploying to $node ==="
    
    # Preview
    rw-blueprint deploy topology.yaml --node $node --dry-run
    
    # Deploy
    rw-blueprint deploy topology.yaml --node $node
    
    # Verify
    ssh sysop@$node "systemctl list-units --type=service --state=running | grep -E 'container|service'"
    
    echo "=== Completed $node ==="
done
```

### Example 4: Emergency Rollback

```bash
# Rollback a specific service
rw-blueprint rollback honcho-api --node infra

# Rollback all services on a node
for service in pgvector honcho-api rw-inference-engine; do
    rw-blueprint rollback $service --node infra
done

# Verify rollback
ssh sysop@infra "systemctl status honcho-api.service"
```

---

## Health Checks

### Automatic Health Checks

After deployment, rw_blueprint runs health checks:

1. **systemd check** — `systemctl is-active <service>`
2. **Port check** — Service port is listening
3. **HTTP check** — Health endpoint returns 200 (if configured)

### Custom Health Checks

Add to topology.yaml:

```yaml
services:
  - id: honcho-api
    node: infra
    kind: application
    image: localhost/honcho:latest
    health_check:
      http:
        url: http://localhost:8000/health
        expected_status: 200
        timeout: 30
      ports:
        - 8000
```

### Manual Health Verification

```bash
# Check all services on node
ssh sysop@infra "systemctl list-units --type=service --state=running"

# Check specific service
ssh sysop@infra "systemctl status honcho-api.service"

# Check container logs
ssh sysop@infra "podman logs honcho-api.container --tail 50"

# Test HTTP endpoint
curl -s http://localhost:8000/health | jq .
```

---

## State Management

### Deployment State Storage

Deployment history is stored in:
```
.rw_blueprint/deployments/
├── infra/
│   ├── honcho-api.json      # Deployment records
│   ├── pgvector.json
│   └── artifacts/           # Stored quadlet files
│       └── honcho-api/
│           └── current/
│               └── honcho-api.container
├── enterprise/
│   └── portainer.json
└── dev/
    └── ...
```

### Viewing Deployment History

```bash
# View all deployment records
cat .rw_blueprint/deployments/infra/honcho-api.json

# Pretty print with jq
cat .rw_blueprint/deployments/infra/honcho-api.json | jq '.[-3:]'

# Check latest deployment
jq '.[-1]' .rw_blueprint/deployments/infra/honcho-api.json
```

### Clearing State

```bash
# Clear all deployment history
rm -rf .rw_blueprint/deployments/*

# Clear specific service history
rm .rw_blueprint/deployments/infra/honcho-api.json
```

---

## Troubleshooting Deployment

### Issue: Deployment hangs

**Check:**
```bash
# See what's running
ssh sysop@infra "ps aux | grep podman"

# Check SSH connection
ssh -v sysop@infra "echo OK" 2>&1 | tail -20

# Kill stuck processes
ssh sysop@infra "pkill -f 'systemctl.*start'"
```

### Issue: Quadlet transfer fails

**Check:**
```bash
# Verify SSH access
ssh sysop@infra "sudo ls -la /etc/containers/systemd/"

# Check disk space
ssh sysop@infra "df -h /etc/containers"

# Manual transfer
scp docs/generated/quadlet/honcho-api.container sysop@infra:/tmp/
ssh sysop@infra "sudo mv /tmp/honcho-api.container /etc/containers/systemd/"
```

### Issue: Service won't start

**Check:**
```bash
# View service logs
ssh sysop@infra "journalctl -u honcho-api.service --no-pager -n 50"

# Check container logs
ssh sysop@infra "podman logs honcho-api.container --tail 50"

# Check port conflicts
ssh sysop@infra "sudo ss -tlnp | grep 8000"

# Manual start
ssh sysop@infra "sudo systemctl start honcho-api.service"
```

### Issue: Health check timeout

**Solution:**
```bash
# Increase timeout in config
# ~/.rw_blueprint/config.yaml
deploy:
  health_check_timeout: 120

# Or skip health check with --force
rw-blueprint deploy topology.yaml --node infra --force
```

---

## Post-Deployment Checklist

After successful deployment:

- [ ] All services show `active (running)` status
- [ ] Health endpoints respond correctly
- [ ] Logs show no errors
- [ ] Deployment history recorded in `.rw_blueprint/deployments/`
- [ ] Quadlet files present in `/etc/containers/systemd/`
- [ ] Firewall rules allow required ports
- [ ] Monitoring/alerting configured
- [ ] Backup procedure documented

---

## Best Practices

1. **Always dry-run first** — Preview changes before applying
2. **Deploy in dependency order** — DB → API → Proxy
3. **Use --force sparingly** — Only for emergency deployments
4. **Monitor health closely** — Watch for failures in first 5 minutes
5. **Keep deployment history** — Don't delete `.rw_blueprint/deployments/`
6. **Test rollback procedure** — Practice before you need it
7. **Document changes** — Update CHANGELOG.md after each deployment

---

## Related Documentation

- [Troubleshooting Guide](troubleshooting.md)
- [Architecture](../../ARCHITECTURE.md)
- [SPEC-004: Deployment Engine](../SPEC-004-deployment-engine.md)
- [SPEC-006: Rollback & Recovery](../SPEC-006-rollback-recovery.md)

---

**Last Updated:** 2026-09-19  
**Maintained by:** RapidWebs Infrastructure Team
