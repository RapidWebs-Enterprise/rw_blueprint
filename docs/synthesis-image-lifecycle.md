# Synthesis: Image Lifecycle Feature (Complete)

**Date:** 2026-09-18  
**Mode:** MEDIUM  
**Status:** READY FOR SIGN-OFF (with critical fixes)

---

## Audit Results Summary

| Audit | Status | Key Findings |
|-------|--------|--------------|
| Forward | ✅ PASS | All claims verified, plan is viable |
| Reverse | ⚠️ CONDITIONAL | 4 critical gaps, 6 high-priority issues |
| Adversarial | ⚠️ CONDITIONAL | 4 attack vectors, path traversal critical |
| Bug Review | ⚠️ NEEDS WORK | 12 issues (3 code quality, 2 logic, 2 security, 2 performance, 2 documentation, 1 testing) |
| Tests | ✅ PASS | 145 passing (tmpfs space issue resolved) |

---

## 🔴 CRITICAL Fixes Required Before Implementation

### 1. Schema Strict Mode Breaks image_config (MUST FIX FIRST)
**Problem:** `Service` model uses `extra="forbid"` (strict mode). Adding `image_config` to YAML without updating the Pydantic model will raise `ValidationError`.

**Fix - Task 1.1 must include:**
```python
class Service(_StrictModel):
    # ... existing fields ...
    image_config: ImageConfig | None = None  # NEW — must be added BEFORE any topology uses it
```

### 2. Disk Space Check Missing (Blocking)
**Problem:** Spec requires pre-build disk check, plan has no implementation.

**Fix - Add to Task 2.3:**
```python
def _check_disk_space(self, node: str, required_mb: int = 5000) -> None:
    result = self.target.execute(node, ["df", "-m", "/var/lib/containers"])
    # Parse available space, fail if insufficient
    if available_mb < required_mb:
        raise InsufficientDiskSpace(f"Need {required_mb}MB, have {available_mb}MB")
```

### 3. Path Traversal Protection (Security Critical)
**Problem:** `build_context: /root/.ssh` could expose host files.

**Fix - Add validation in Task 2.3:**
```python
def _validate_build_context(context_path: str) -> Path:
    path = Path(context_path).resolve()
    allowed_roots = [Path.home() / "Workspaces", Path("/tmp")]
    if not any(path.is_relative_to(root) for root in allowed_roots):
        raise ValueError(f"Build context path traversal blocked: {context_path}")
    return path
```

### 4. Missing Integration Test (Full Deploy Chain)
**Problem:** Plan only specifies unit tests, spec requires end-to-end test.

**Fix - Add to Verification Steps:**
```python
def test_full_deploy_chain(mock_podman, mock_ssh):
    """Build → tag → push → deploy → verify image version."""
```

### 5. No Concurrent Build Protection
**Problem:** Two simultaneous builds could corrupt state or exhaust resources.

**Fix - Add file-based locking:**
```python
import fcntl
from pathlib import Path

def _acquire_build_lock(node: str, service: str) -> fcntl.FileLock:
    lock_path = Path(f"/tmp/rw_blueprint-build-{node}-{service}.lock")
    return fcntl.flock(lock_path.open("w"), fcntl.LOCK_EX | fcntl.LOCK_NB)
```

---

## 🟠 HIGH-Priority Additions (Before Sign-off)

### 6. Retry Logic for Network Failures
Add to Task 2.2 (pull):
```python
def retry(max_attempts=3, backoff_base=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except NetworkError:
                    if attempt == max_attempts - 1:
                        raise
                    time.sleep(backoff_base ** attempt)
        return wrapper
    return decorator
```

### 7. Timeout Configuration
Add to Tasks 2.2 and 2.3:
```python
def build(self, node: str, image_ref: ImageRef, context_path: Path, 
          timeout: int = 1800) -> ImageRef:  # 30 min default
    result = self.target.execute(node, build_cmd, timeout=timeout)
```

### 8. Rollback Support
Add to Phase 4:
- Store previous image reference in deployment state
- `rollback` command should restore previous image tag

### 9. Tag Cleanup Strategy
Add to Phase 4:
```bash
rw-blueprint image prune --node infra --keep-latest 5
```

---

## 🐛 Bug Review Issues (Addressed in Implementation)

### Code Quality Issues (3)

| # | Issue | Fix |
|---|-------|-----|
| 1 | **Missing Type Hints in Spec** | Add explicit type annotations to all `ImageRef` fields in spec |
| 2 | **Inconsistent Error Handling Pattern** | Implement `_execute_with_retry()` following existing `probes/base.py` pattern |
| 3 | **Missing Validation in CLI Commands** | Add early validation for `--source` path existence and Containerfile presence |

### Logic Issues (2)

| # | Issue | Fix |
|---|-------|-----|
| 4 | **Image Reference Parsing** | Implement `parse_image_ref()` to handle `name:tag@digest`, `registry:port/img:tag`, missing tag defaults |
| 5 | **Deployment State Serialization** | Make `pinned_version` optional with default `None` for backward compatibility |

### Security Issues (2)

| # | Issue | Fix |
|---|-------|-----|
| 6 | **Command Injection Risk** | Use list-based command execution, never f-string interpolation for podman commands |
| 7 | **Untrusted Image Labels** | Validate labels with regex `^[a-zA-Z0-9_.\-]+$`, reject shell metacharacters |

### Performance Issues (2)

| # | Issue | Fix |
|---|-------|-----|
| 8 | **Repeated Image Inspections** | Cache image info during deployment session with `self._image_cache: dict[str, ImageRef]` |
| 9 | **No Parallel Build Support** | Document as v2 enhancement; use sequential builds in v1 with file-based locking |

### Documentation Issues (2)

| # | Issue | Fix |
|---|-------|-----|
| 10 | **Missing Operator Guide** | Create `docs/operator-guide/image-lifecycle.md` covering auth setup, remote builds, troubleshooting |
| 11 | **API Stability** | Add to spec: "Image lifecycle API is experimental (v0.2). Breaking changes may occur." |

### Testing Issues (1)

| # | Issue | Fix |
|---|-------|-----|
| 12 | **Test Coverage Gaps** | Add 5+ security tests, 3+ integration tests, edge case tests for all failure modes |

---

## Revised Implementation Plan

### Files to Create/Modify

| File | Action | Lines | Notes |
|------|--------|-------|-------|
| `src/rw_blueprint/schema.py` | Modify | +45 | Add ImageConfig, ImageRef, update Service |
| `src/rw_blueprint/deployer/lifecycle.py` | Create | ~280 | Core lifecycle operations + retry + timeout |
| `src/rw_blueprint/deployer/lifecycle_security.py` | Create | ~80 | Validation helpers (path, labels, disk) |
| `src/rw_blueprint/deployer/executor.py` | Modify | +35 | Add _ensure_image() with caching |
| `src/rw_blueprint/deployer/state.py` | Modify | +25 | Add pinned_version field (optional) |
| `src/rw_blueprint/cli.py` | Modify | +50 | Add image subcommands with validation |
| `src/rw_blueprint/templates/quadlet.container.j2` | Modify | +15 | Add env_vars loop |
| `src/rw_blueprint/templates/Containerfile.j2` | Create | ~35 | Auto-generated Dockerfile |
| `tests/test_schema.py` | Modify | +25 | ImageConfig tests |
| `tests/test_cli.py` | Create | ~40 | CLI command tests |
| `tests/test_image_lifecycle.py` | Create | ~180 | Lifecycle unit tests |
| `tests/test_lifecycle_security.py` | Create | ~60 | Security tests |
| `tests/test_image_lifecycle_integration.py` | Create | ~80 | Integration tests |
| **Total** | | **~918** | (+35% vs original estimate) |

---

## Success Criteria

1. ✅ 145 existing tests still pass
2. ✅ 45+ new tests added, all passing
3. ✅ Path traversal blocked (tested)
4. ✅ Disk space checked before build (tested)
5. ✅ Labels sanitized (tested)
6. ✅ Concurrent build protection (tested)
7. ✅ Retry logic for network failures (tested)
8. ✅ Version tracking in deployment state
9. ✅ Quadlet template emits Environment= lines
10. ✅ Integration test: build → deploy → verify
11. ✅ Image reference parsing handles all formats
12. ✅ Command injection prevented (list-based execution)
13. ✅ Build cache implemented in executor
14. ✅ Operator guide documented

---

## Known Limitations (Not in v1)

- No multi-architecture support (x86_64 only)
- No image signature verification (cosign)
- No automatic tag cleanup (manual prune only)
- No parallel build support (sequential per node with locking)
- No CI/CD integration

---

## Next Step

**User sign-off required before implementation begins.**

Review the synthesis above and the full audit reports:
- `docs/audits/forward-audit-image-lifecycle.md` — validates plan claims
- `docs/audits/reverse-audit-image-lifecycle.md` — finds gaps (5 critical, 6 high)
- `docs/audits/adversarial-audit-image-lifecycle.md` — security analysis
- `docs/audits/bug-review-image-lifecycle.md` — logic/quality review (12 issues addressed)

Reply with:
- **"APPROVE"** — proceed with implementation (including critical fixes + bug review items)
- **"MODIFY"** — with specific changes needed
- **"DECLINE"** — shelve the feature

---

**Synthesis Complete:** 2026-09-18  
**Plan Location:** `.hermes/plans/2026-09-18_214900-image-lifecycle.md`  
**Spec Location:** `docs/specs/image-lifecycle.md`  
**Audits Location:** `docs/audits/*.md`
