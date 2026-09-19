# Reverse Audit: Image Lifecycle Feature

**Auditor**: Reverse Audit Subagent  
**Date**: 2026-09-18  
**Target**: `/home/sysop/Workspaces/rw_blueprint/.hermes/plans/2026-09-18_214900-image-lifecycle.md`  
**Spec Reference**: `/home/sysop/Workspaces/rw_blueprint/docs/specs/image-lifecycle.md`

---

## Executive Summary

The implementation plan covers the happy path well but has **critical gaps in backward compatibility, error handling, and operational safety**. The most severe issue is that the current `Service` model uses `extra="forbid"` (strict mode), which will **reject any topology containing `image_config`** until the schema is explicitly updated. Additionally, the plan lacks concrete implementations for disk space checks, concurrent build protection, path validation, and tag cleanup — all of which are mentioned in the spec's edge cases table but absent from the task breakdown.

---

## 🔴 CRITICAL Findings

### 1. Backward Compatibility Break — Strict Schema Will Reject image_config

**Location**: `src/rw_blueprint/schema.py:52-55`, Plan Task 1.1

The `Service` model inherits from `_StrictModel` which sets `ConfigDict(extra="forbid")`. The plan says to "Add optional `image_config` field to `Service` model" but **does not explicitly state that this field must be added before any topology using it can be parsed**.

**Current reality**: Adding `image_config` to the YAML without adding it to the Pydantic model will raise `ValidationError: Extra inputs are not permitted`.

**Risk**: Any topology update that includes `image_config` will fail validation. This is a breaking change if not handled in the correct order.

**Recommendation**: Task 1.1 must explicitly include:
```python
class Service(_StrictModel):
    # ... existing fields ...
    image_config: ImageConfig | None = None  # NEW — must be added here
```

---

### 2. No Disk Space Check Implementation

**Location**: Spec Section "Edge Cases & Error Handling", Plan Phase 2

The spec explicitly states: "Disk full — Check available space before build, fail early". However, **no task in the plan implements this check**. Task 2.3 (`build_image`) does not mention disk space validation.

**Risk**: Builds can consume all disk space, causing system instability and failing other services.

**Recommendation**: Add to Task 2.3:
```python
def _check_disk_space(node: str, required_mb: int) -> None:
    """Check if target node has sufficient disk space."""
    result = self.target.execute(node, ["df", "-m", "/var/lib/containers"])
    # Parse output, compare available vs required
    if available_mb < required_mb:
        raise InsufficientDiskSpace(f"Need {required_mb}MB, have {available_mb}MB")
```

---

### 3. No Path Traversal Protection in Build Context

**Location**: Spec Section "Security Considerations" #1, Plan Task 2.3

The spec mentions "Build context path validation — prevent path traversal attacks" but the plan provides **no implementation details** for how this validation occurs.

**Risk**: Malicious `build_context` values like `/../../../etc/passwd` could expose host files to the build process.

**Recommendation**: Add explicit path validation to Task 2.3:
```python
from pathlib import Path

def _validate_build_context(context_path: str) -> Path:
    """Validate build context path prevents traversal."""
    path = Path(context_path).resolve()
    # Ensure path is within allowed directories
    allowed_roots = [Path.home(), Path("/tmp"), Path("/var/lib/rw_blueprint")]
    if not any(path.is_relative_to(root) for root in allowed_roots):
        raise ValueError(f"Build context path traversal blocked: {context_path}")
    if not path.exists():
        raise FileNotFoundError(f"Build context not found: {context_path}")
    return path
```

---

### 4. Missing Integration Test for Full Deploy Chain

**Location**: Spec Section "Testing Strategy" — Integration Tests, Plan Verification Steps

The spec lists "End-to-end build → inspect → deploy" as an integration test requirement, but the plan's testing section only mentions "Mock executor with missing image, verify lifecycle called" (Task 3.1). There is **no actual end-to-end test specified**.

**Risk**: The feature could pass all unit tests but fail in production when build, push, pull, and deploy interact.

**Recommendation**: Add explicit integration test task:
```python
def test_full_deploy_chain(mock_podman, mock_ssh):
    """Build → tag → push → deploy → verify image version."""
    # 1. Build image from source
    # 2. Push to registry  
    # 3. Deploy topology referencing pushed image
    # 4. Verify deployment state contains correct git SHA
    # 5. Verify service is running with expected image
```

---

## 🟠 HIGH Findings

### 5. No Concurrent Build Protection

**Location**: Plan Phase 2, Bug Review checklist item "Race conditions in concurrent builds"

If two services are deployed simultaneously and both trigger builds, they could:
- Compete for disk space
- Cause OOM kills
- Produce conflicting layer caches

The plan mentions "Race conditions in concurrent builds" in the Bug Review checklist but provides **no implementation to prevent or serialize concurrent builds**.

**Recommendation**: Add file-based lock or queue mechanism:
```python
import fcntl
from pathlib import Path

def _acquire_build_lock(node: str, service: str) -> fcntl.FileLock:
    lock_path = Path(f"/tmp/rw_blueprint-build-{node}-{service}.lock")
    return fcntl.flock(lock_path.open("w"), fcntl.LOCK_EX | fcntl.LOCK_NB)
```

---

### 6. No Tag Cleanup / Image Pruning Strategy

**Location**: Spec nowhere explicitly, but implied by operational reality

The plan has no mechanism to clean up:
- Dangling image tags after rebuilds
- Old semantic version tags that are no longer deployed
- Untagged intermediate build layers

**Risk**: Node disk fills with orphaned images over time. After 100 deployments, each with 5 tags, that's 500+ image references per service.

**Recommendation**: Add to Phase 4 (Polish):
```bash
# Suggested command
rw-blueprint image prune --node infra --keep-latest 5
rw-blueprint image prune --dangling --node infra
```

---

### 7. Incomplete Error Handling for Network Failures

**Location**: Plan Task 2.2 (pull), Spec "Network failure during pull — Retry 3x with exponential backoff"

The spec mentions retry logic but the plan's Task 2.2 only says "Handle authentication" and "Verify pulled image". There is **no retry mechanism specified**.

**Risk**: Transient network blips cause deployment failures requiring manual retry.

**Recommendation**: Add to Task 2.2:
```python
import time
from functools import wraps

def retry(max_attempts=3, backoff_base=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except NetworkError as e:
                    if attempt == max_attempts - 1:
                        raise
                    time.sleep(backoff_base ** attempt)
        return wrapper
    return decorator
```

---

### 8. No Timeout Configuration for Long-Running Operations

**Location**: Plan Task 2.2, 2.3

Podman pull and build operations can hang indefinitely. The current `TargetManager.execute()` has a hardcoded 30-second timeout, but builds often exceed this.

**Risk**: Builds timing out silently, or hanging forever blocking deployment.

**Recommendation**: Add timeout parameter to lifecycle methods:
```python
def build(self, node: str, image_ref: ImageRef, context_path: Path, 
          timeout: int = 1800) -> ImageRef:  # 30 min default
    result = self.target.execute(node, build_cmd, timeout=timeout)
```

---

### 9. Missing Rollback Support for Image Changes

**Location**: Spec nowhere, but critical for "we can't afford to be breaking anything"

If a new image build fails or produces a broken service, there's no documented rollback path. The existing `RollbackExecutor` reverts quadlet configs but doesn't handle image rollback.

**Risk**: Broken image stuck in production with no automated recovery.

**Recommendation**: Add to Phase 4:
- Store previous image reference in deployment state
- `rollback` command should restore previous image tag and restart service

---

### 10. No Build Cache Invalidation Strategy

**Location**: Plan nowhere, Spec "Stale cache after rebuild" in Bug Review

If source code changes but the build context path remains the same, podman may use cached layers and produce a stale image. The plan doesn't address cache busting.

**Recommendation**: Add to Task 2.3:
```python
# Option 1: Use --no-cache flag for important builds
# Option 2: Add BUILD_CACHE_BUST=timestamp build arg
# Option 3: Compute content hash of context and pass as cache-bust arg
```

---

## 🟡 MEDIUM Findings

### 11. CLI Design — Ambiguous `image inspect` Syntax

**Location**: Spec Section 2, Plan Task 1.2

The spec shows:
```bash
rw-blueprint image inspect honcho-api
```

This uses a **service ID**, not an image reference. But the lifecycle class expects an `ImageRef`. The mapping from service ID to image reference is unclear.

**Better design**:
```bash
rw-blueprint image inspect honcho-api        # Looks up service's current image
rw-blueprint image inspect localhost/honcho:v2.1.3  # Explicit reference
```

**Recommendation**: Clarify in Task 1.2 that `image inspect <service-id>` should resolve the service's configured image first.

---

### 12. Missing `--registry` Flag in Pull Command

**Location**: Spec Section 2, Plan Task 2.2

The spec shows:
```bash
rw-blueprint image pull honcho-api --registry ghcr.io --tag v2.1.3
```

But podman's `pull` command expects the full reference: `ghcr.io/rapidwebs-ent/honcho:v2.1.3`. The plan doesn't specify how `--registry` and `--tag` combine into the full image reference.

**Recommendation**: Document the reference construction logic:
```python
def _resolve_pull_reference(service_id: str, registry: str, tag: str) -> str:
    # Look up service's image_config.source
    # Prepend registry if different from default
    # Append tag
    return f"{registry}/{source}:{tag}"
```

---

### 13. No Authentication Error Diagnosis

**Location**: Plan Task 2.2, Spec "Auth failure — Clear error message pointing to ~/.containers/auth.json"

The spec mentions clear error messages but the plan doesn't specify what those messages should say.

**Recommendation**: Add explicit error handling:
```python
except AuthenticationError as e:
    raise ClickException(
        f"Registry authentication failed: {e}\n\n"
        f"Ensure ~/.containers/auth.json exists and is valid.\n"
        f"Run 'podman login {registry}' to authenticate."
    )
```

---

### 14. Missing Multi-Node Build Strategy

**Location**: Spec Open Question #2, Plan nowhere

The spec asks: "Should build happen on workstation and push to infra, or build directly on infra?" The plan assumes "Direct build on infra" but doesn't document this decision or its implications.

**Risk**: If builds are done on infra, workstation resources aren't utilized. If builds are done locally, push strategy is needed.

**Recommendation**: Add explicit decision record:
```markdown
## Decision: Build on Target Node
- Rationale: Simpler pipeline, no push/pull round-trip
- Trade-off: Infra node resources used for builds
- Future: Support local build + push for faster iteration
```

---

### 15. No Version Display in `deploy --plan` Output

**Location**: Plan Task 4.1, Spec Success Criteria #3

The spec success criteria states: "`rw-blueprint deploy` checks image version and reports if mismatched". But Task 4.1 only mentions "Display version in `rw-blueprint deploy --plan` output".

**Gap**: Where does the version check happen? During plan generation? During execution? The plan doesn't specify.

**Recommendation**: Add version check to `PlanGenerator` or executor:
```python
def _check_image_version(service: Service, node: str) -> str | None:
    """Return mismatch description if deployed image differs from desired."""
    deployed = self.lifecycle.inspect(node, service.image)
    if deployed and deployed.git_sha != desired_sha:
        return f"Image mismatch: deployed={deployed.git_sha}, desired={desired_sha}"
    return None
```

---

### 16. Quadlet Template Environment Variables Not Addressed

**Location**: Plan Task 3.2, Current Template

The current `quadlet.container.j2` template has **no environment variable support**:
```
[Container]
Image={{ service.image }}
PublishPort=...
```

The plan says to "Add env_vars loop to emit Environment= lines" but the current template doesn't even have a placeholder for where env vars would go.

**Recommendation**: Update template to include env vars section:
```jinja
[Container]
Image={{ service.image }}
{% for p in service.ports %}PublishPort={{ p.host_port }}:{{ p.port }}
{% endfor %}
{% if service.env_vars %}
{% for key, value in service.env_vars.items() %}Environment={{ key }}={{ value }}
{% endfor %}
{% endif %}
```

---

### 17. No Containerfile Template Specification

**Location**: Plan Task 2.3, Template file creation

The plan mentions creating `src/rw_blueprint/templates/Containerfile.j2` but doesn't specify its content. What does a generated Containerfile look like?

**Risk**: Generated Containerfiles may be invalid or insecure.

**Recommendation**: Define template structure:
```dockerfile
# Generated by rw_blueprint — DO NOT EDIT
FROM {{ base_image }}
WORKDIR /app
COPY . /app
{% for arg in build_args %}ARG {{ arg }}={{ build_args[arg] }}
{% endfor %}
RUN pip install -r requirements.txt
EXPOSE {{ ports | join(' ') }}
CMD ["python", "main.py"]
```

---

## 🟢 LOW Findings

### 18. Missing Help Text for New CLI Commands

**Location**: Plan Task 1.2

The new `image` subcommand group needs comprehensive help text explaining:
- What each command does
- When to use build vs pull
- How tagging works
- Auth requirements

**Recommendation**: Add to Task 1.2:
```python
@app.group(help="Manage container images: list, inspect, build, pull, push, prune.")
def image():
    pass

@image.command()
def list():
    """List images available on target nodes."""
```

---

### 19. No Logging Strategy for Build Operations

**Location**: Plan Phase 2

Build operations produce verbose output that should be captured for debugging. The plan doesn't specify logging behavior.

**Recommendation**: Add logging to Task 2.3:
```python
import logging
logger = logging.getLogger("rw_blueprint.lifecycle")

def build_image(...):
    logger.info(f"Starting build for {image_ref.name}:{image_ref.tag}")
    # Capture podman output
    # Log build progress
    logger.info(f"Build completed: {image_ref.digest}")
```

---

### 20. Missing Exit Code Consistency

**Location**: Plan Task 1.2, Current CLI patterns

The existing CLI uses exit code 2 for validation errors. The new image commands should follow the same convention but the plan doesn't specify.

**Recommendation**: Document exit codes:
- 0: Success
- 1: Operational error (build failed, pull failed)
- 2: Validation error (invalid args, missing config)

---

## 📋 Complete Findings List

| # | Finding | Severity | Location | Recommendation |
|---|---------|----------|----------|----------------|
| 1 | Schema strict mode rejects image_config | 🔴 Critical | schema.py:52, Plan Task 1.1 | Add field explicitly before YAML changes |
| 2 | No disk space check implementation | 🔴 Critical | Plan Phase 2 | Add _check_disk_space() to Task 2.3 |
| 3 | No path traversal protection | 🔴 Critical | Plan Task 2.3 | Add _validate_build_context() |
| 4 | Missing end-to-end integration test | 🔴 Critical | Spec Testing, Plan Verification | Add test_full_deploy_chain() |
| 5 | No concurrent build protection | 🟠 High | Plan Phase 2 | Add file-based locking |
| 6 | No tag cleanup/pruning | 🟠 High | Plan Phase 4 | Add image prune command |
| 7 | No retry for network failures | 🟠 High | Plan Task 2.2 | Add retry decorator with backoff |
| 8 | No timeout configuration | 🟠 High | Plan Tasks 2.2, 2.3 | Add timeout param to lifecycle methods |
| 9 | No rollback for image changes | 🟠 High | Plan Phase 4 | Extend RollbackExecutor |
| 10 | No build cache invalidation | 🟠 High | Plan Task 2.3 | Add cache-bust mechanism |
| 11 | Ambiguous image inspect syntax | 🟡 Medium | Spec Section 2, Plan Task 1.2 | Clarify service ID resolution |
| 12 | Missing --registry flag logic | 🟡 Medium | Plan Task 2.2 | Document reference construction |
| 13 | No auth error diagnosis | 🟡 Medium | Plan Task 2.2 | Add specific error messages |
| 14 | No multi-node build strategy | 🟡 Medium | Spec Open Q #2 | Document build location decision |
| 15 | No version mismatch detection | 🟡 Medium | Plan Task 4.1 | Add check to PlanGenerator |
| 16 | Quadlet template missing env support | 🟡 Medium | Plan Task 3.2 | Update template with env vars loop |
| 17 | No Containerfile template spec | 🟡 Medium | Plan Task 2.3 | Define template structure |
| 18 | Missing help text | 🟢 Low | Plan Task 1.2 | Add comprehensive help |
| 19 | No logging strategy | 🟢 Low | Plan Phase 2 | Add logger to lifecycle |
| 20 | Exit code inconsistency | 🟢 Low | Plan Task 1.2 | Document exit code convention |

---

## Recommendations for Plan Revision

### Before Implementation (Blocking)

1. **Update Task 1.1** to explicitly show the `image_config` field addition to `Service` model
2. **Add disk space check** to Task 2.3 implementation details
3. **Add path validation** to Task 2.3 implementation details
4. **Add integration test** to Verification Steps section
5. **Add concurrent build locking** to Task 2.3 or as new Task 2.4

### Before Sign-off (High Priority)

6. Add retry logic to Task 2.2
7. Add timeout configuration to Tasks 2.2 and 2.3
8. Document rollback strategy for image failures
9. Specify cache invalidation approach
10. Clarify CLI syntax for `image inspect` and `image pull`

### Nice to Have (Phase 4 or Later)

11. Add image prune command
12. Add comprehensive help text
13. Add logging throughout
14. Define Containerfile template structure
15. Document multi-node build decision

---

## Backward Compatibility Checklist

- [ ] `image_config` field added to `Service` model before any topology uses it
- [ ] Existing topologies without `image_config` still parse (field is optional)
- [ ] Default `tag_strategy="latest"` preserves current behavior
- [ ] New CLI commands don't interfere with existing commands
- [ ] `DeploymentRecord` schema evolution handles missing `pinned_version`
- [ ] Quadlet template changes don't break existing generated units
- [ ] All 145 existing tests still pass after changes

---

## Verification Steps (Added)

1. **Schema validation**: `rw-blueprint validate topology.yaml` passes with and without `image_config`
2. **Path traversal test**: Attempt build with `../../etc` context — should be rejected
3. **Disk full test**: Simulate low disk, verify build fails with clear error
4. **Network failure test**: Kill connection during pull, verify retry works
5. **Concurrent build test**: Deploy two services simultaneously, verify no corruption
6. **Integration test**: Build → push → deploy → verify image SHA matches source commit
7. **Rollback test**: Deploy broken image, verify rollback restores previous version
8. **Tag cleanup test**: Build 10 versions, verify old tags don't accumulate indefinitely

---

*Audit completed: 2026-09-18*  
*Next step: Forward audit to validate claims against actual codebase*
