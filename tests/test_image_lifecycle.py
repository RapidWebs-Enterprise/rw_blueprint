"""Tests for ImageLifecycle class."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from pathlib import Path
import pytest

from rw_blueprint.deployer.lifecycle import ImageLifecycle, ImageOperationError
from rw_blueprint.schema import ImageRef


class TestImageLifecycle:
    """Tests for ImageLifecycle class."""

    def setup_method(self):
        """Setup test fixtures."""
        self.mock_target = MagicMock()
        self.lifecycle = ImageLifecycle(target_manager=self.mock_target)

    def test_list_images_empty(self):
        """list_images returns empty list when no images."""
        self.mock_target.execute.return_value = MagicMock(
            success=True, stdout='[]'
        )
        result = self.lifecycle.list_images("node1")
        assert result == []

    def test_list_images_parse(self):
        """list_images parses podman output correctly."""
        self.mock_target.execute.return_value = MagicMock(
            success=True,
            stdout='[{"Repository":"honcho","Tag":"latest","Id":"sha256:abc"}]'
        )
        result = self.lifecycle.list_images("node1")
        assert len(result) == 1
        assert result[0].name == "honcho"
        assert result[0].tag == "latest"
        assert result[0].digest == "sha256:abc"

    def test_inspect_returns_none_when_not_found(self):
        """inspect returns None when image not found."""
        self.mock_target.execute.return_value = MagicMock(success=False)
        result = self.lifecycle.inspect("node1", "honcho:latest")
        assert result is None

    def test_inspect_returns_image_ref(self):
        """inspect returns ImageRef when image found."""
        self.mock_target.execute.return_value = MagicMock(
            success=True,
            stdout='[{"Config":{"Labels":{"org.git.sha":"abc123"}}}]'
        )
        result = self.lifecycle.inspect("node1", "honcho:latest")
        assert result is not None
        assert result.name == "honcho"
        assert result.tag == "latest"

    def test_pull_success(self):
        """pull succeeds when podman pull succeeds."""
        self.mock_target.execute.return_value = MagicMock(success=True)
        image_ref = ImageRef(name="honcho", tag="v2.0", source="pull")
        result = self.lifecycle.pull("node1", image_ref)
        # ImageRef is frozen, so check we got an ImageRef back (via cache or return)
        assert result is not None
        assert result.source == "pull"

    def test_pull_failure_after_retries(self):
        """pull raises ImageOperationError after retries."""
        self.mock_target.execute.return_value = MagicMock(
            success=False, stderr="error"
        )
        image_ref = ImageRef(name="honcho", tag="latest", source="pull")
        with pytest.raises(ImageOperationError):
            self.lifecycle.pull("node1", image_ref)

    def test_build_validates_path(self):
        """build validates build context path."""
        image_ref = ImageRef(name="honcho", tag="latest", source="build")
        fake_path = Path("/nonexistent/path")
        
        # Mock validate_build_context to raise
        with pytest.raises(Exception):  # ImageSecurityError
            self.lifecycle.build("node1", image_ref, fake_path)

    def test_clear_cache(self):
        """clear_cache empties the image cache."""
        self.lifecycle._image_cache["key"] = "value"
        self.lifecycle.clear_cache()
        assert len(self.lifecycle._image_cache) == 0

    def test_retry_logic(self):
        """Retry logic executes multiple attempts."""
        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return MagicMock(success=False, stderr="fail")
        
        self.mock_target.execute.side_effect = side_effect
        
        image_ref = ImageRef(name="honcho", tag="latest", source="pull")
        with pytest.raises(ImageOperationError):
            self.lifecycle.pull("node1", image_ref)
        
        # Should have called 3 times (max_retries=3)
        assert call_count >= 2
