"""Security validation helpers for image lifecycle.

Provides path traversal protection, label sanitization, and disk space checks.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path


logger = logging.getLogger(__name__)


# Validation patterns
LABEL_PATTERN = re.compile(r'^[a-zA-Z0-9_.\-]+$')
ALLOWED_BUILD_ROOTS = [Path.home() / "Workspaces"]


class ImageSecurityError(Exception):
    """Raised when image security validation fails."""
    pass


class InsufficientDiskSpace(ImageSecurityError):
    """Raised when there's not enough disk space for a build."""
    pass


def validate_build_context(context_path: str) -> Path:
    """Validate build context path to prevent path traversal attacks.

    Args:
        context_path: Path to the build context directory.

    Returns:
        Resolved absolute path if valid.

    Raises:
        ImageSecurityError: If path traversal detected or path doesn't exist.
    """
    path = Path(context_path).resolve()

    # Check existence
    if not path.exists():
        raise ImageSecurityError(f"Build context does not exist: {context_path}")

    if not path.is_dir():
        raise ImageSecurityError(f"Build context is not a directory: {context_path}")

    # Check against allowed roots (path traversal protection)
    if not any(str(path).startswith(str(root)) for root in ALLOWED_BUILD_ROOTS):
        raise ImageSecurityError(
            f"Build context path traversal blocked: {context_path}. "
            f"Allowed roots: {[str(r) for r in ALLOWED_BUILD_ROOTS]}"
        )

    return path


def validate_label(key: str, value: str) -> bool:
    """Validate image label key/value pair.

    Args:
        key: Label key.
        value: Label value.

    Returns:
        True if valid, False otherwise.
    """
    return bool(LABEL_PATTERN.match(key)) and bool(LABEL_PATTERN.match(value))


def sanitize_labels(labels: dict[str, str]) -> dict[str, str]:
    """Sanitize labels by removing invalid key/value pairs.

    Args:
        labels: Raw labels from topology.yaml.

    Returns:
        Filtered labels with only valid entries.
    """
    sanitized = {}
    for key, value in labels.items():
        if validate_label(key, str(value)):
            sanitized[key] = str(value)
        else:
            logger.warning("Dropped invalid label: key=%s value=%s", key, value)
    return sanitized


def check_disk_space(node: str, required_mb: int = 5000) -> bool:
    """Check if there's enough disk space for a build.

    Args:
        node: Target node identifier.
        required_mb: Minimum required space in MB.

    Returns:
        True if sufficient space.

    Raises:
        InsufficientDiskSpace: If not enough space.
    """
    import subprocess
    from rw_blueprint.deployer.targets import TargetManager

    tm = TargetManager({node: {"host": node}})
    result = tm.execute(node, ["df", "-BG", "/var/lib/containers"], sudo=True)
    if not result.success:
        # Fallback: assume sufficient if we can't check
        logger.warning("Could not check disk space for %s, assuming OK", node)
        return True

    available_mb = parse_disk_space_output(result.stdout)
    if available_mb < required_mb:
        raise InsufficientDiskSpace(
            f"Insufficient disk space on {node}: {available_mb}MB available, "
            f"{required_mb}MB required"
        )
    return True


def parse_disk_space_output(output: str) -> int:
    """Parse df output to get available space in MB.

    Args:
        output: Raw df command output.

    Returns:
        Available space in MB.
    """
    # Parse "Filesystem      1K-blocks     Used Available Use% Mounted"
    lines = output.strip().split("\n")
    if len(lines) < 2:
        return 0

    # Get the available column (4th column, 1K blocks)
    parts = lines[1].split()
    if len(parts) >= 4:
        try:
            available_kb = int(parts[3])
            return available_kb // 1024  # Convert to MB
        except (ValueError, IndexError):
            pass
    return 0
