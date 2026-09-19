# SPEC-006: Rollback and Recovery

**Status**: Proposed  
**Created**: 2026-09-15  
**Parent**: SPEC-004 (Deployment Engine)

## 1. Problem Statement

Deployments fail. Services crash. We need to be able to revert to a known good state quickly.

## 2. Goals

- [x] Track deployment history per service per node
- [x] Support manual rollback to previous version
- [x] Support automatic rollback on health check failure
- [x] Preserve deployment artifacts for rollback
- [x] Log all rollback actions

## 3. Design

### 3.1 Deployment State Tracking

```json
{
  "node": "infra",
  "service": "caddy",
  "deployments": [
    {
      "version": "1.0.0",
      "deployed_at": "2026-09-15T10:00:00Z",
      "deployed_by": "sysop",
      "status": "healthy",
      "image": "localhost/caddy-cloudflare:latest",
      "config_hash": "sha256:abc123..."
    },
    {
      "version": "1.1.0",
      "deployed_at": "2026-09-15T14:30:00Z",
      "deployed_by": "automation",
      "status": "failed",
      "rollback_reason": "health_check_timeout"
    }
  ]
}
```

### 3.2 Rollback Triggers

| Trigger | Action | Approval Required |
|---------|--------|-------------------|
| Health check failure (auto) | Immediate rollback | No |
| Manual rollback command | Rollback to previous | Yes (prod) |
| Deployment script failure | Abort + rollback | No |
| User-initiated | Rollback to specific version | Yes |

### 3.3 Rollback Procedure

1. Identify previous healthy version from deployment history
2. Stop current service: `systemctl stop caddy.container`
3. Remove current quadlet: `rm /etc/containers/systemd/caddy.container`
4. Restore previous quadlet (if stored)
5. Reload systemd: `systemctl daemon-reload`
6. Start previous service: `systemctl start caddy.container`
7. Verify health
8. Log rollback completion

### 3.4 Artifact Preservation

Store deployed quadlet files in versioned directory:

```
/var/lib/rw-blueprint/artifacts/
├── infra/
│   ├── caddy/
│   │   ├── v1.0.0/
│   │   │   └── caddy.container
│   │   └── v1.1.0/
│   │       └── caddy.container (failed)
│   └── honcho-api/
│       └── v1.0.0/
│           └── honcho-api.container
```

## 4. Recovery Scenarios

### 4.1 Service Won't Start

1. Check journal logs: `journalctl -u caddy.container`
2. Verify quadlet file syntax: `podman quadlet --dryrun`
3. Check dependencies are running
4. Retry with extended timeout

### 4.2 Service Starts but Crashes

1. Enable restart policy: `Restart=on-failure`
2. Check health endpoint
3. Review application logs
4. Consider rollback

### 4.3 Full Node Recovery

After node reboot:
1. Deployment engine reconciles desired vs actual
2. Missing services are started
3. Failed services are restarted
4. Drift is reported

## 5. Testing Requirements

- [ ] Test rollback on health check failure
- [ ] Test manual rollback command
- [ ] Test artifact preservation
- [ ] Test recovery after node reboot
- [ ] Test partial rollback (some services succeed, others fail)
