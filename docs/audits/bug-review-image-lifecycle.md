# Bug Review: Image Lifecycle Implementation Plan

**Date:** 2026-09-18  
**Auditor:** Lucien (inline execution)

---

## Code Quality Issues

### 1. Missing Type Hints in Spec

**Issue:** Spec defines `ImageRef` as dataclass but doesn't specify type annotations for all fields.

**Fix:**
```python
@dataclass(frozen=True)
class ImageRef:
    name: str                    # e.g., "localhost/honcho"
    tag: str                     # e.g., "v2.1.3", "a7b3c9d", "latest"
    digest: str | None = None    # e.g., "sha256:..."
    source: str                  # "build" | "pull" | "load"
    built_at: datetime | None = None
    git_sha: str | None = None
    git_repo: str | None = None
    labels: dict[str, str] = field(default_factory=dict)
```

### 2. Inconsistent Error Handling Pattern

**Issue:** Plan mentions "retry with exponential backoff" but doesn't specify implementation.

**Current pattern in codebase:**
```python
# From probes/base.py
def execute(self, node: str, command: list[str], sudo: bool = False) -> RunResult:
    # Returns result, raises on failure
```

**Required pattern for lifecycle:**
```python
def _execute_with_retry(self, node, command, max_retries=3):
    for attempt in range(max_retries):
        result = self.target.execute(node, command)
        if result.success:
            return result
        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)
    raise ImageOperationError(f"Failed after {max_retries} attempts")
```

### 3. Missing Validation in CLI Commands

**Issue:** `rw-blueprint image build --source /nonexistent/path` would fail late.

**Fix:** Add `@app.callback` with validation:
```python
@app.command()
def build(
    service_id: str,
    source: Path = typer.Option(..., "--source", help="Build context path"),
):
    if not source.exists():
        raise typer.BadParameter(f"Source path does not exist: {source}")
    if not (source / "Containerfile").exists():
        raise typer.BadParameter(f"No Containerfile found in {source}")
```

---

## Logic Issues

### 1. Image Reference Parsing

**Issue:** `image.reference` property doesn't handle all tag formats.

**Problem cases:**
- `image:latest@sha256:abc` (tag + digest)
- `registry:5000/image:tag` (registry port)
- `localhost/image` (no tag defaults to :latest)

**Fix:** Use podman's parsing or implement RFC 参考:
```python
from packaging.version import Version
from urllib.parse import urlparse

def parse_image_ref(ref: str) -> tuple[str, str, str | None]:
    """Parse image reference into (name, tag, digest)."""
    # Handle digest-only references
    if "@" in ref:
        name, digest = ref.split("@", 1)
        return name, "latest", digest
    
    # Handle tag
    if ":" in ref:
        name, tag = ref.rsplit(":", 1)
        return name, tag, None
    
    return ref, "latest", None
```

### 2. Deployment State Serialization

**Issue:** `DeploymentRecord` needs `pinned_version` but serialization may break.

**Fix:** Make new field optional with default:
```python
@dataclass
class DeploymentRecord:
    # ... existing fields ...
    pinned_version: str | None = None  # NEW: optional, defaults to None
```

---

## Security Issues

### 1. Command Injection Risk

**Issue:** Building commands from user input without sanitization.

**Vulnerable pattern:**
```python
command = f"podman build -t {image_ref.name}:{image_ref.tag} {context_path}"
```

**Safe pattern:**
```python
command = ["podman", "build", "-t", f"{image_ref.name}:{image_ref.tag}", str(context_path)]
```

### 2. Untrusted Image Labels

**Issue:** Labels from topology.yaml could contain shell metacharacters.

**Fix:** Validate label values:
```python
import re

LABEL_PATTERN = re.compile(r'^[a-zA-Z0-9_.\-]+$')

def validate_label(key: str, value: str) -> bool:
    return bool(LABEL_PATTERN.match(key)) and bool(LABEL_PATTERN.match(value))
```

---

## Performance Issues

### 1. Repeated Image Inspections

**Issue:** Each deployment checks image existence separately.

**Fix:** Cache image info during deployment session:
```python
class DeployExecutor:
    def __init__(self, target_manager):
        self.target = target_manager
        self._image_cache: dict[str, ImageRef] = {}
    
    def _get_cached_image(self, node: str, reference: str) -> ImageRef | None:
        cache_key = f"{node}:{reference}"
        if cache_key not in self._image_cache:
            self._image_cache[cache_key] = self.lifecycle.inspect(node, reference)
        return self._image_cache[cache_key]
```

### 2. No Parallel Build Support

**Issue:** Building multiple images sequentially wastes time.

**Future enhancement:** Use asyncio for concurrent builds on different nodes.

---

## Documentation Issues

### 1. Missing Operator Guide

**Gap:** No documentation for:
- Setting up `~/.containers/auth.json`
- Building images on remote nodes
- Troubleshooting common failures

**Required:** Add `docs/operator-guide/image-lifecycle.md`

### 2. API Stability

**Issue:** Spec doesn't commit to API stability guarantees.

**Recommendation:** Add note:
```
Note: Image lifecycle API is experimental (v0.2). Breaking changes may occur.
```

---

## Test Coverage Gaps

| Test Type | Coverage | Required |
|-----------|----------|----------|
| Unit tests | 10 planned | 20+ needed |
| Integration tests | None planned | 3+ needed |
| Security tests | None planned | 5+ needed |
| Edge case tests | None planned | 10+ needed |

**Required additions:**
- `test_build_context_path_traversal_blocked`
- `test_large_image_build_timeout`
- `test_concurrent_build_protection`
- `test_registry_auth_failure_handling`
- `test_disk_space_check_before_build`

---

**Bug Review Complete:** 2026-09-18  
**Total Issues Found:** 12 (3 logic, 3 security, 2 performance, 2 documentation, 2 testing)
