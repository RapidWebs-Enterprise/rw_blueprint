"""Image lifecycle management for rw_blueprint.

Provides build, pull, tag, push, and inspection of container images
on target nodes via podman CLI.
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from rw_blueprint.deployer.lifecycle_security import (
    InsufficientDiskSpace,
    ImageSecurityError,
    check_disk_space,
    sanitize_labels,
    validate_build_context,
)
from rw_blueprint.deployer.targets import RunResult, TargetManager
from rw_blueprint.schema import ImageRef


class RetryableError(Exception):
    """Base class for errors that should trigger retry."""
    pass


class NetworkError(RetryableError):
    """Raised when network operations fail."""
    pass


class ImageOperationError(Exception):
    """Raised when image operations fail after retries."""
    pass


class PodmanClient(Protocol):
    """Protocol for podman CLI interaction."""

    def execute(self, node: str, command: list[str], sudo: bool = False) -> RunResult:
        ...


@dataclass
class BuildResult:
    """Result of an image build operation."""

    success: bool
    image_ref: ImageRef | None
    error: str | None = None
    build_log: str = ""


class ImageLifecycle:
    """Manage container image lifecycle on target nodes.

    Supports building from source, pulling from registries, and managing
    image versions with git provenance tracking.
    """

    def __init__(self, target_manager: TargetManager, max_retries: int = 3):
        self.target = target_manager
        self.max_retries = max_retries
        self._image_cache: dict[str, ImageRef] = {}

    def list_images(self, node: str) -> list[ImageRef]:
        """List all images on target node.

        Args:
            node: Target node identifier.

        Returns:
            List of ImageRef objects for all local images.
        """
        result = self.target.execute(node, ["podman", "images", "--format", "json"])
        if not result.success:
            return []

        images = []
        try:
            data = json.loads(result.stdout)
            for img in data:
                images.append(ImageRef(
                    name=img.get("Repository", ""),
                    tag=img.get("Tag", "latest"),
                    digest=img.get("Id"),
                    source="pull",
                ))
        except (json.JSONDecodeError, KeyError):
            pass

        return images

    def inspect(self, node: str, reference: str) -> ImageRef | None:
        """Get metadata for a specific image.

        Args:
            node: Target node identifier.
            reference: Image reference (name:tag).

        Returns:
            ImageRef if found, None otherwise.
        """
        cache_key = f"{node}:{reference}"
        if cache_key in self._image_cache:
            return self._image_cache[cache_key]

        result = self.target.execute(node, ["podman", "inspect", reference])
        if not result.success:
            return None

        try:
            data = json.loads(result.stdout)
            if not data:
                return None

            img = data[0]
            refs = ImageRef(
                name=reference.split(":")[0],
                tag=reference.split(":")[-1] if ":" in reference else "latest",
                source="pull",
                built_at=datetime.now(),
                labels=self._extract_labels(img),
            )
            self._image_cache[cache_key] = refs
            return refs
        except (json.JSONDecodeError, KeyError):
            return None

    def pull(self, node: str, image_ref: ImageRef) -> ImageRef:
        """Pull image from registry to target node.

        Args:
            node: Target node identifier.
            image_ref: Image reference to pull.

        Returns:
            Updated ImageRef with pull metadata.

        Raises:
            ImageOperationError: If pull fails after retries.
        """
        ref_string = image_ref.reference
        last_error = None

        for attempt in range(self.max_retries):
            try:
                result = self.target.execute(
                    node,
                    ["podman", "pull", ref_string],
                    timeout=300,
                )
                if result.success:
                    return ImageRef(
                        name=image_ref.name,
                        tag=image_ref.tag,
                        digest=image_ref.digest,
                        source="pull",
                        built_at=datetime.now(),
                        git_sha=image_ref.git_sha,
                        git_repo=image_ref.git_repo,
                        labels=image_ref.labels,
                    )
                last_error = result.stderr
            except Exception as e:
                last_error = str(e)

            if attempt < self.max_retries - 1:
                time.sleep(2 ** attempt)

        raise ImageOperationError(f"Failed to pull {ref_string}: {last_error}")

    def build(
        self,
        node: str,
        image_ref: ImageRef,
        context_path: Path,
        containerfile: Path | None = None,
        build_args: dict[str, str] | None = None,
        timeout: int = 1800,
    ) -> ImageRef:
        """Build image from source on target node.

        Args:
            node: Target node identifier.
            image_ref: Target image reference.
            context_path: Local path to build context.
            containerfile: Optional Containerfile path.
            build_args: Additional build arguments.
            timeout: Build timeout in seconds.

        Returns:
            Updated ImageRef with build metadata.

        Raises:
            ImageSecurityError: If build context validation fails.
            InsufficientDiskSpace: If insufficient disk space.
            ImageOperationError: If build fails.
        """
        # Security: validate build context
        validated_path = validate_build_context(str(context_path))

        # Security: check disk space
        if not check_disk_space(node):
            raise InsufficientDiskSpace(
                f"Insufficient disk space on {node} for build"
            )

        # Build command using list form (prevents injection)
        cmd = ["podman", "build", "-t", image_ref.reference]

        if containerfile:
            cmd.extend(["-f", str(containerfile)])

        if build_args:
            for arg_name, arg_value in build_args.items():
                cmd.extend(["--build-arg", f"{arg_name}={arg_value}"])

        # Add labels
        sanitized_labels = sanitize_labels(image_ref.labels)
        for key, value in sanitized_labels.items():
            cmd.extend(["--label", f"{key}={value}"])

        cmd.append(str(validated_path))

        # Execute with retry
        last_error = None
        for attempt in range(self.max_retries):
            try:
                result = self.target.execute(
                    node, cmd, timeout=timeout, sudo=True
                )
                if result.success:
                    return ImageRef(
                        name=image_ref.name,
                        tag=image_ref.tag,
                        digest=image_ref.digest,
                        source="build",
                        built_at=datetime.now(),
                        git_sha=self._get_git_sha(context_path),
                        git_repo=self._get_git_repo(context_path),
                        labels=image_ref.labels,
                    )
                last_error = result.stderr
            except Exception as e:
                last_error = str(e)

            if attempt < self.max_retries - 1:
                time.sleep(2 ** attempt)

        raise ImageOperationError(f"Failed to build {image_ref.reference}: {last_error}")

    def push(self, image_ref: ImageRef, registry: str | None = None) -> None:
        """Push image to registry.

        Args:
            image_ref: Image reference to push.
            registry: Target registry URL (uses image_ref.source if None).

        Raises:
            ImageOperationError: If push fails.
        """
        target = registry or image_ref.source
        if not target:
            raise ImageOperationError("No registry specified for push")

        cmd = ["podman", "push", image_ref.reference, target]

        result = self.target.execute("localhost", cmd)
        if not result.success:
            raise ImageOperationError(f"Failed to push {image_ref.reference}: {result.stderr}")

    def tag(self, image_ref: ImageRef, new_tag: str) -> None:
        """Add tag to existing image.

        Args:
            image_ref: Source image reference.
            new_tag: New tag to add.
        """
        cmd = ["podman", "tag", image_ref.reference,
               f"{image_ref.name}:{new_tag}"]

        result = self.target.execute("localhost", cmd)
        if not result.success:
            raise ImageOperationError(f"Failed to tag {image_ref.reference} as {new_tag}")

    def inspect_image(self, node: str, image_ref: ImageRef) -> dict:
        """Get detailed image metadata.

        Args:
            node: Target node identifier.
            image_ref: Image to inspect.

        Returns:
            Raw metadata dictionary from podman inspect.
        """
        result = self.target.execute(node, ["podman", "inspect", image_ref.reference])
        if not result.success:
            return {}
        try:
            return json.loads(result.stdout)[0]
        except (json.JSONDecodeError, IndexError):
            return {}

    def _extract_labels(self, inspect_data: dict) -> dict[str, str]:
        """Extract labels from podman inspect output."""
        config = inspect_data.get("Config", {})
        labels = config.get("Labels", {}) or {}
        return {k: v for k, v in labels.items() if v}

    def _get_git_sha(self, context_path: Path) -> str | None:
        """Get current git SHA from build context."""
        try:
            result = subprocess.run(
                ["git", "-C", str(context_path), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return None

    def _get_git_repo(self, context_path: Path) -> str | None:
        """Get git remote URL from build context."""
        try:
            result = subprocess.run(
                ["git", "-C", str(context_path), "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return None

    def clear_cache(self) -> None:
        """Clear the image cache."""
        self._image_cache.clear()
