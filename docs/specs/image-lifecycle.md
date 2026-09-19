# Image Lifecycle Feature — Technical Spec

**Status:** DRAFT  
**Date:** 2026-09-18  
**Author:** Lucien (RapidWebs Agent Team)

---

## Problem Statement

Currently, rw_blueprint treats container images as opaque strings. When deploying honcho-api, the topology.yaml simply says `image: localhost/honcho:latest`. There is no:
- Automation for pulling images from registries
- Build pipeline from source code
- Version tracking (which git commit produced which image)
- Push/pull lifecycle management

This means manual intervention is required for every image update, and there's no audit trail linking deployed services to source code versions.

---

## Proposed Solution

Add an **ImageLifecycle** subsystem to the deployer module that provides:
1. **Image inspection** — What's available locally and on remote nodes
2. **Image pulling** — From remote registries with auth
3. **Image building** — From source with version tagging
4. **Image pushing** — To registries for distribution
5. **Version tracking** — Git SHA → image tag mapping in deployment state

---

## Interface Contracts

### ImageRef Model

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
    
    @property
    def reference(self) -> str:
        """Full image reference: name:tag@digest"""
        ref = f"{self.name}:{self.tag}"
        if self.digest:
            ref += f"@{self.digest}"
        return ref
```

### ImageConfig Model (for topology.yaml)

```python
@dataclass
class ImageConfig:
    """Optional image configuration for a service."""
    source: str | None = None           # Registry URL
    build_context: str | None = None    # Local path or git URL
    tag_strategy: str = "latest"        # "latest" | "git-sha" | "semver"
    labels: dict[str, str] = field(default_factory=dict)
    build_args: dict[str, str] = field(default_factory=dict)
```

### Lifecycle Protocol

```python
class ImageLifecycle:
    """Manage container image lifecycle on target nodes."""
    
    def __init__(self, target_manager: TargetManager):
        self.target = target_manager
    
    def list_images(self, node: str) -> list[ImageRef]:
        """List all images on target node."""
    
    def inspect(self, node: str, reference: str) -> ImageRef | None:
        """Get metadata for a specific image."""
    
    def pull(self, node: str, image_ref: ImageRef) -> ImageRef:
        """Pull image from registry to target node."""
    
    def build(
        self, 
        node: str, 
        image_ref: ImageRef,
        context_path: Path,
        containerfile: Path | None = None,
        build_args: dict[str, str] | None = None
    ) -> ImageRef:
        """Build image from source on target node."""
    
    def push(self, image_ref: ImageRef) -> None:
        """Push image to registry."""
    
    def tag(self, image_ref: ImageRef, new_tag: str) -> None:
        """Add tag to existing image."""
```

---

## Implementation Phases

### Phase 1: Foundation
- Add ImageConfig to schema
- Add CLI image subcommand group
- Implement stub methods (NotImplementedError)

### Phase 2: Core Operations
- Implement `list_images()` via `podman images --format=json`
- Implement `inspect()` via `podman inspect`
- Implement `pull()` via `podman pull`
- Implement `build()` via `podman build`
- Add Containerfile.j2 template for auto-generation

### Phase 3: Integration
- Integrate into DeployExecutor (`_ensure_image()`)
- Fix quadlet template to emit Environment= lines
- Add version tracking to deployment state

### Phase 4: Polish
- Add push support (optional for now)
- Add tag strategies (git-sha, semver)
- Add error handling and retries

---

## Dependency Graph

```
Phase 1 → Phase 2 → Phase 3 → Phase 4
    ↓           ↓          ↓          ↓
  schema     lifecycle  executor   polish
   + CLI      + build    + state
              + pull
```

---

## Edge Cases & Error Handling

| Scenario | Behavior |
|----------|----------|
| Image exists locally | Skip pull/build, use existing |
| Network failure during pull | Retry 3x with exponential backoff, then fail |
| Build fails | Return error with podman stderr |
| Disk full | Check available space before build, fail early |
| Auth failure | Clear error message pointing to ~/.containers/auth.json |
| Missing build context | Validate path exists before starting build |
| Tag collision | Overwrite or error (configurable) |

---

## Security Considerations

1. **Build context path validation** — prevent path traversal attacks
2. **Image label sanitization** — don't trust untrusted labels
3. **Registry credentials** — store in `~/.containers/auth.json`, never in topology.yaml
4. **Privilege escalation** — podman requires sudo on target; executor already handles this

---

## Backward Compatibility

- `image_config` is optional — existing topologies work unchanged
- Default tag_strategy is "latest" — matches current behavior
- No breaking changes to existing CLI commands

---

## Testing Strategy

### Unit Tests (target: 20+)
- `test_image_ref_creation`
- `test_image_ref_reference_property`
- `test_list_images_parse_output`
- `test_inspect_returns_none_for_missing`
- `test_pull_success`
- `test_pull_failure_retry`
- `test_build_with_labels`
- `test_build_generates_containerfile`
- `test_tag_strategy_git_sha`
- `test_tag_strategy_semver`

### Integration Tests
- End-to-end build → inspect → deploy
- Multi-node build verification
- Version tracking across deployments

---

## Success Criteria

1. ✅ `rw-blueprint image list --node infra` shows honcho:latest with git SHA
2. ✅ `rw-blueprint image build honcho-api --source /home/sysop/honcho` produces tagged image
3. ✅ `rw-blueprint deploy` checks image version and reports if mismatched
4. ✅ Deployment state tracks which git commit is deployed
5. ✅ All 145 existing tests still pass
6. ✅ 20+ new tests added and passing

---

## Files Reference

- **Top-level:** `/home/sysop/Workspaces/rw_blueprint/topology.yaml`
- **Schema:** `/home/sysop/Workspaces/rw_blueprint/src/rw_blueprint/schema.py`
- **Deployer:** `/home/sysop/Workspaces/rw_blueprint/src/rw_blueprint/deployer/`
- **Templates:** `/home/sysop/Workspaces/rw_blueprint/src/rw_blueprint/templates/`
- **CLI:** `/home/sysop/Workspaces/rw_blueprint/src/rw_blueprint/cli.py`
- **Tests:** `/home/sysop/Workspaces/rw_blueprint/tests/`

---

## Open Questions

1. Should we support multi-arch builds? (Probably not for now — infra is x86_64 only)
2. Should build happen on workstation and push to infra, or build directly on infra? (Direct build on infra is simpler for now)
3. How to handle registry auth for private images? (Use standard podman auth file, document requirement)
