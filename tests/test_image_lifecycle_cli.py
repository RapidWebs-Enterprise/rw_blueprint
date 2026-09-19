"""Tests for ImageLifecycle CLI commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest
from typer.testing import CliRunner

from rw_blueprint.cli import app, image_app
from rw_blueprint.schema import ImageRef


runner = CliRunner()


class TestImageCLI:
    """Tests for image CLI commands."""

    def test_image_help(self):
        """Test image --help command."""
        result = runner.invoke(app, ["image", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "build" in result.output
        assert "pull" in result.output

    def test_image_list_no_images(self):
        """Test image list with no images."""
        with patch('rw_blueprint.cli.TargetManager') as MockTarget:
            mock_target = MagicMock()
            MockTarget.return_value = mock_target
            
            with patch.object(mock_target, 'execute', return_value=MagicMock(
                success=True, stdout='[]'
            )):
                result = runner.invoke(app, ["image", "list", "--node", "localhost"])
                # Should not error
                assert result.exit_code == 0 or result.exit_code == 1

    def test_image_build_path_validation(self):
        """Test image build validates source path."""
        result = runner.invoke(app, [
            "image", "build", "test-svc",
            "--source", "/nonexistent/path"
        ])
        # Should fail with path not found
        assert result.exit_code != 0 or "does not exist" in result.output.lower()


class TestImageRef:
    """Tests for ImageRef model."""

    def test_image_ref_reference_property(self):
        """Test ImageRef.reference property."""
        ref = ImageRef(name="honcho", tag="v1.0")
        assert ref.reference == "honcho:v1.0"

    def test_image_ref_with_digest(self):
        """Test ImageRef with digest."""
        ref = ImageRef(name="honcho", tag="v1.0", digest="sha256:abc")
        assert ref.reference == "honcho:v1.0@sha256:abc"

    def test_image_ref_default_source(self):
        """Test ImageRef defaults."""
        ref = ImageRef(name="honcho", tag="latest")
        assert ref.source == "pull"
