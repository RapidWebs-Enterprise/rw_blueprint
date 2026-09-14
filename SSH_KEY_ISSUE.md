# SSH Key Issue — Investigation

**Date**: 2026-09-14
**Status**: Identified blocker

## Problem

SSH from workstation to Incus containers (infra, dev, enterprise) via Tailscale IPs works for some commands but fails for `incus list` on remote hosts.

## Current State

| Host | Tailscale IP | SSH Status | incus Available |
|------|-------------|------------|-----------------|
| srv1 (host) | 100.68.224.116 | ✅ Works | ✅ Yes |
| infra (container) | 100.79.58.118 | ✅ Works | ❌ `command not found` |
| dev (container) | 100.127.203.36 | ✅ Works | ❌ `command not found` |
| enterprise (container) | 100.65.82.48 | ✅ Works | ❌ `command not found` |

## Root Cause

`incus` CLI is installed on the srv1 host only, not inside the containers. The containers run `podman` (for service containers like honcho, rw-inference) but not `incus` (which manages the VMs on the host).

## Probe Results

### srv1 (full suite)
- incus: ✅ 3 containers detected
- podman: ✅ 0 containers (no rootless podman)
- port: ✅ 12 ports, 11 links
- tailscale: ✅ 5 peers
- dns: ❌ 1 error (rapidwebs.org timeout)

### infra/dev/enterprise (partial)
- incus: ❌ Not available (not installed in containers)
- podman: ✅ Running (honcho, rw-inference, etc.)
- port: ✅ Listening ports detected
- tailscale: ✅ Peers visible
- dns: ❌ Same timeout issue

## Recommended Fixes

1. **For incus data**: Use srv1 host's `incus list` output (already captured)
2. **For podman data inside containers**: Add podman SSH fallback to probes
3. **For DNS**: Investigate network routing from workstation

## Live State Files

- `docs/live-srv1.json` — Full state
- `docs/live-infra.json` — Partial (no incus)
- `docs/live-dev.json` — Partial (no incus)
- `docs/live-enterprise.json` — Partial (no incus)

## Next Steps

If full container-level observation is needed:
1. Install `incus` inside each container, OR
2. Query srv1's incus for all VM/container data (already working)
3. Add podman SSH probe that works inside containers
