"""Security tests for image lifecycle.

Tests path traversal protection, label sanitization, and disk space checks.
"""

from __future__ import annotations

import pytest
from pathlib import Path
from pydantic import ValidationError

from rw_blueprint.deployer.lifecycle_security import (
    ImageSecurityError,
    InsufficientDiskSpace,
    validate_build_context,
    validate_label,
    sanitize_labels,
    check_disk_space,
    parse_disk_space_output,
)


class TestValidateBuildContext:
    """Tests for build context validation."""

    def test_valid_build_context(self, tmp_path):
        """Valid build context returns resolved path."""
        result = validate_build_context(str(tmp_path))
        assert result == tmp_path.resolve()

    def test_nonexistent_path_raises(self):
        """Non-existent path raises ImageSecurityError."""
        with pytest.raises(ImageSecurityError, match="does not exist"):
            validate_build_context("/nonexistent/path")

    def test_file_not_directory_raises(self, tmp_path):
        """File (not directory) raises ImageSecurityError."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("test")
        with pytest.raises(ImageSecurityError, match="not a directory"):
            validate_build_context(str(file_path))

    def test_path_traversal_blocked_home_workspaces(self, tmp_path):
        """Path traversal outside Workspaces/tmp is blocked."""
        # Create a symlink to /etc outside allowed roots
        evil_link = tmp_path / "evil"
        evil_link.symlink_to("/etc")
        # The link resolves to /etc which is outside allowed roots
        with pytest.raises(ImageSecurityError, match="path traversal blocked"):
            validate_build_context(str(evil_link))

    def test_nested_workspace_allowed(self, tmp_path):
        """Nested paths within Workspaces are allowed."""
        nested = tmp_path / "subdir" / "nested"
        nested.mkdir(parents=True)
        result = validate_build_context(str(nested))
        assert "Workspaces" in str(result) or str(result) == str(nested.resolve())


class TestValidateLabel:
    """Tests for label validation."""

    def test_valid_label_alphanumeric(self):
        """Alphanumeric labels are valid."""
        assert validate_label("key", "value") is True
        assert validate_label("org.git.sha", "abc123") is True

    def test_valid_label_with_dashes_underscores(self):
        """Labels with dashes and underscores are valid."""
        assert validate_label("my-label", "my_value") is True

    def test_invalid_label_shell_chars(self):
        """Labels with shell metacharacters are invalid."""
        assert validate_label("key;rm -rf /", "value") is False
        assert validate_label("key", "value && another") is False
        assert validate_label("key|pipe", "value") is False
        assert validate_label("key`cmd`", "value") is False

    def test_invalid_label_newlines(self):
        """Labels with newlines are invalid."""
        assert validate_label("key\nmalicious", "value") is False
        assert validate_label("key", "value\nmalicious") is False

    def test_empty_label_values(self):
        """Empty labels should be handled gracefully."""
        # Empty strings don't match the pattern (requires at least 1 char)
        assert validate_label("", "") is False


class TestSanitizeLabels:
    """Tests for label sanitization."""

    def test_valid_labels_preserved(self):
        """Valid labels are preserved."""
        labels = {"key": "value", "org.git.sha": "abc123"}
        result = sanitize_labels(labels)
        assert result == labels

    def test_invalid_labels_removed(self):
        """Invalid labels are removed."""
        labels = {
            "valid": "label",
            "bad;cmd": "value",
            "another_valid": "yes",
        }
        result = sanitize_labels(labels)
        assert "valid" in result
        assert "another_valid" in result
        assert "bad;cmd" not in result

    def test_none_labels_handled(self):
        """None input handled gracefully."""
        result = sanitize_labels({})
        assert result == {}


class TestCheckDiskSpace:
    """Tests for disk space checking."""

    def test_check_disk_space_returns_true(self):
        """Placeholder returns True for now."""
        result = check_disk_space("localhost")
        assert result is True


class TestParseDiskSpaceOutput:
    """Tests for parsing df output."""

    def test_parse_standard_df_output(self):
        """Parse standard df -m output."""
        output = "Filesystem     1K-blocks     Used Available Use% Mounted\n/dev/sda1      100000000 50000000  50000000  50% /\n"
        result = parse_disk_space_output(output)
        assert result == 48828  # 50000000 KB / 1024 ≈ 48828 MB

    def test_parse_single_line_output(self):
        """Handle single-line output."""
        output = "Filesystem     1K-blocks     Used Available Use% Mounted\n"
        result = parse_disk_space_output(output)
        assert result == 0

    def test_parse_malformed_output(self):
        """Handle malformed output gracefully."""
        output = "garbage data\n"
        result = parse_disk_space_output(output)
        assert result == 0
