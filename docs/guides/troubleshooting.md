# Troubleshooting Guide

**Version:** 0.2.0  
**Last Updated:** 2026-09-19

---

## Quick Diagnosis

### Common Issues at a Glance

| Symptom | Likely Cause | Solution |
|---------|-------------|----------|
| `FileNotFoundError: topology.yaml` | Wrong path or missing file | Verify file exists with `ls -la` |
| `ValidationError` on load | Schema mismatch | Check schema_version matches 0.2 |
| SSH connection fails | Key not configured | Verify `~/.ssh/id_ed25519` exists |
| Probe timeout | Network unreachable | Check Tailscale mesh connectivity |
| Port conflict on deploy | Service already running | Use `--force` or stop existing service |
| Health check fails | Service not ready | Check logs with `podman logs <service>` |
| Rollback fails | No previous version | Check `.rw_blueprint/deployments/` |

---

## Installation Issues

### Problem: `pip install` fails with dependency conflicts

**Cause:** Python version mismatch or missing build tools

**Solution:**
```bash
# Use uv instead (recommended)
uv pip install -e ".[dev,mcp]"

# Or specify Python version
python3.11 -m pip install -e ".[dev,mcp]"

# Clean install
uv pip uninstall rw-blueprint
uv pip install -e ".[dev,mcp]"
```

### Problem: `rw-blueprint` command not found

**Cause:** Virtual environment not activated or package not installed correctly

**Solution:**
```bash
# Activate venv
source .venv/bin/activate

# Verify installation
which rw-blueprint
rw-blueprint --version

# Reinstall if needed
pip install -e ".[mcp]"
```

### Problem: `uv run pytest` fails with import errors

**Cause:** Package not installed in development mode

**Solution:**
```bash
# Install in editable mode
uv pip install -e "."

# Verify imports work
python -c "from rw_blueprint.schema import Topology; print('OK')"
```

---

## Topology Validation Issues

### Problem: `ValidationError: Extra inputs are not permitted`

**Cause:** Schema version mismatch or unknown fields

**Solution:**
```yaml
# Ensure correct schema version at top of topology.yaml
schema_version: '0.2'

# Remove any unknown fields
# Valid top-level keys: schema_version, metadata, zones, nodes, services, links, dependencies
```

### Problem: `ValidationError: node 'X' references unknown zone 'Y'`

**Cause:** Zone ID mismatch between node declaration and zone definition

**Solution:**
```yaml
# Fix: Ensure zone is defined before referenced
zones:
  - id: infra        # Define this first
    name: Infrastructure

nodes:
  - id: infra        # Then reference it
    zone: infra      # Must match zone.id exactly
```

### Problem: `ValidationError: service 'X' references unknown node 'Y'`

**Cause:** Node ID typo or missing node declaration

**Solution:**
```bash
# List all nodes to verify IDs
rw-blueprint validate topology.yaml

# Check for typos in node references
grep "node:" topology.yaml | sort -u
```

### Problem: `ValidationError: duplicate X id 'Y'`

**Cause:** Duplicate ID in zones, nodes, services, links, or dependencies

**Solution:**
```bash
# Find duplicates
grep -n "id:" topology.yaml | sort | uniq -d

# Fix: Ensure all IDs are unique within their type
```

---

## Probe Issues

### Problem: Probe timeout on remote node

**Cause:** SSH connectivity issues or network timeout

**Solution:**
```bash
# Test SSH connectivity manually
ssh sysop@100.79.58.118 "echo OK"

# Increase probe timeout
rw-blueprint probe --nodes infra --timeout 60

# Check SSH config
cat ~/.ssh/config | grep -A3 "Host infra"
```

### Problem: `FileNotFoundError: incus` or `podman`

**Cause:** Required CLI tools not installed on target node

**Solution:**
```bash
# On target node, install required tools
ssh sysop@infra "sudo apt update && sudo apt install -y incus podman tailscale"

# Verify installations
ssh sysop@infra "incus version && podman --version && tailscale version"
```

### Problem: Tailscale IP resolution fails

**Cause:** Tailscale not connected or DNS resolution issue

**Solution:**
```bash
# Check Tailscale status on target
ssh sysop@infra "tailscale status"

# Test DNS resolution
ssh sysop@infra "tailscale ping 100.79.58.118"

# Restart Tailscale if needed
ssh sysop@infra "sudo systemctl restart tailscaled"
```

### Problem: DNS probe fails for `rapidwebs.org`

**Cause:** Workstation cannot resolve production DNS

**Solution:**
```bash
# Use Tailscale IP instead of domain
# In topology.yaml, use tailscale_ip instead of domain name

# Or add DNS server to resolver
echo "nameserver 100.100.100.100" | sudo tee /etc/resolv.conf
```

---

## Deployment Issues

### Problem: `RuntimeError: Quadlet file not found`

**Cause:** Artifacts not generated before deployment

**Solution:**
```bash
# Generate artifacts first
rw-blueprint generate topology.yaml --output docs/generated/

# Verify quadlet files exist
ls -la docs/generated/quadlet/

# Then deploy
rw-blueprint deploy topology.yaml --node infra
```

### Problem: `Failed to start service: Unit <service>.container not found`

**Cause:** Quadlet file not transferred or systemd not reloaded

**Solution:**
```bash
# Check if quadlet exists on remote
ssh sysop@infra "ls -la /etc/containers/systemd/<service>.container"

# Manual reload if needed
ssh sysop@infra "sudo systemctl daemon-reload"

# Try deploy again
rw-blueprint deploy topology.yaml --node infra --force
```

### Problem: Port conflict on deployment

**Cause:** Another service already using the port

**Solution:**
```bash
# Check what's using the port
ssh sysop@infra "sudo ss -tlnp | grep <port>"

# Stop conflicting service
ssh sysop@infra "sudo systemctl stop <conflicting-service>"

# Deploy with force (skip port check)
rw-blueprint deploy topology.yaml --node infra --force
```

### Problem: Health check fails after deployment

**Cause:** Service not yet ready or misconfigured

**Solution:**
```bash
# Check service logs
ssh sysop@infra "podman logs <service>.container"

# Check systemd status
ssh sysop@infra "systemctl status <service>.container"

# Manual health check
curl http://localhost:8000/health

# Auto-rollback will trigger if --force not used
# Use --force to skip auto-rollback
rw-blueprint deploy topology.yaml --node infra --force
```

### Problem: Auto-rollback triggers unexpectedly

**Cause:** Health check timeout too short or service slow to start

**Solution:**
```bash
# Increase health check timeout in config
# ~/.rw_blueprint/config.yaml
deploy:
  health_check_timeout: 120  # Default is 30

# Or disable auto-rollback
rw-blueprint deploy topology.yaml --node infra --force
```

---

## Image Lifecycle Issues

### Problem: `Build context path traversal blocked`

**Cause:** Build context outside allowed roots (`/home/*/Workspaces/*`, `/tmp/*`)

**Solution:**
```bash
# Move source to allowed location
mv /path/to/source /home/sysop/Workspaces/my-project

# Rebuild
rw-blueprint image build my-service --source /home/sysop/Workspaces/my-project --node infra
```

### Problem: `Insufficient disk space`

**Cause:** Not enough space on target node

**Solution:**
```bash
# Check disk space
ssh sysop@infra "df -h /var/lib/containers"

# Prune unused images
ssh sysop@infra "podman system prune -f"

# Or increase threshold
# Edit lifecycle.py: required_mb = 5000 -> 2000
```

### Problem: Image pull fails with auth error

**Cause:** Registry credentials not configured

**Solution:**
```bash
# Configure registry auth
ssh sysop@infra "sudo podman login ghcr.io -u <username> -p <token>"

# Or use unauthenticated pull for public repos
rw-blueprint image pull myimage:latest --registry docker.io
```

### Problem: `Failed to build image`

**Cause:** Containerfile issues or missing dependencies

**Solution:**
```bash
# Check build logs
ssh sysop@infra "podman build --log-format json /path/to/source 2>&1 | tail -50"

# Test build manually
ssh sysop@infra "cd /path/to/source && podman build -t test:latest ."

# Verify Containerfile exists
ssh sysop@infra "cat /path/to/source/Containerfile"
```

---

## Rollback Issues

### Problem: `No previous healthy version found`

**Cause:** No deployment history or all previous deployments failed

**Solution:**
```bash
# Check deployment history
cat .rw_blueprint/deployments/<node>/<service>.json

# If history exists but is corrupt, manually restore
ssh sysop@infra "systemctl start <service>.container"
```

### Problem: Rollback fails to restore quadlet

**Cause:** Artifact not preserved or file corrupted

**Solution:**
```bash
# Check stored artifacts
ls -la .rw_blueprint/deployments/<node>/artifacts/<service>/

# If artifacts missing, redeploy to recreate
rw-blueprint deploy topology.yaml --node infra

# Then rollback again
rw-blueprint rollback <service> --node infra
```

---

## MCP Server Issues

### Problem: MCP server fails to start

**Cause:** Port conflict or configuration error

**Solution:**
```bash
# Check if port is in use
ss -tlnp | grep 8765

# Kill conflicting process
sudo fuser -k 8765/tcp

# Start with different port
rw-blueprint-mcp --port 8766
```

### Problem: Tools not appearing in agent

**Cause:** Server not responding or wrong transport

**Solution:**
```bash
# Test server directly
curl http://localhost:8765/lifecycle

# Verify MCP tools registered
rw-blueprint-mcp --help

# Check agent configuration
# Ensure transport type matches (stdio vs SSE)
```

---

## Performance Issues

### Problem: Probes taking too long

**Cause:** Many nodes or slow SSH connections

**Solution:**
```bash
# Run probes in parallel (default)
rw-blueprint probe --nodes node1,node2,node3

# Reduce parallelism if overwhelmed
# Edit probes/multi_node.py: max_concurrent = 5 -> 2

# Increase timeout for slow nodes
rw-blueprint probe --nodes infra --timeout 60
```

### Problem: High memory usage during deployment

**Cause:** Large topology or many concurrent operations

**Solution:**
```bash
# Monitor memory usage
watch -n 1 'free -h'

# Deploy services one at a time
rw-blueprint deploy topology.yaml --node infra --services pgvector

# Then deploy remaining services
rw-blueprint deploy topology.yaml --node infra --services honcho-api,caddy
```

---

## Debug Mode

### Enable verbose logging

```bash
# Set debug environment variable
export RUST_LOG=debug
export PYTHONPATH=src
export RW_BLUEPRINT_DEBUG=1

# Run with verbose output
rw-blueprint --verbose deploy topology.yaml --node infra
```

### Capture debug information

```bash
# Get system info
rw-blueprint --version
python --version
uname -a

# Check SSH connectivity
ssh -v sysop@infra "echo OK" 2>&1 | grep -E "Connecting|Authenticated|debug1"

# Collect probe data
rw-blueprint probe --nodes all --output /tmp/debug-probe.json

# Get deployment state
cat .rw_blueprint/deployments/infra/*.json
```

---

## Getting Help

If you can't find a solution here:

1. **Check existing issues:** https://github.com/RapidWebs-Enterprise/rw_blueprint/issues
2. **Search logs:** `journalctl -u rw-blueprint` or check container logs
3. **Run diagnostic:**
   ```bash
   rw-blueprint --version
   python -c "import rw_blueprint; print(rw_blueprint.__version__)"
   ls -la docs/generated/
   cat .rw_blueprint/deployments/*/ 2>/dev/null
   ```
4. **Open an issue** with:
   - Command run
   - Error output
   - Topology snippet (redacted)
   - System info (`uname -a`, Python version)
