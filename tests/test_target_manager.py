"""Tests for target manager (SSH connections)."""

from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import MagicMock, patch

import pytest

from rw_blueprint.deployer.targets import RunResult, TargetManager


def _make_result(returncode: int = 0, stdout: str = "ok", stderr: str = "") -> CompletedProcess:
    """Helper to create a CompletedProcess mock."""
    return MagicMock(spec=CompletedProcess, returncode=returncode, stdout=stdout, stderr=stderr)


class TestTargetManager:
    """Test TargetManager SSH operations."""

    @patch("rw_blueprint.deployer.targets.run")
    def test_execute_success(self, mock_run):
        """Test successful command execution."""
        mock_run.return_value = _make_result(returncode=0, stdout="active", stderr="")

        manager = TargetManager({"infra": {"host": "100.79.58.118"}})
        result = manager.execute("infra", ["systemctl", "is-active", "caddy"])

        assert result.success is True
        assert result.stdout == "active"
        assert result.returncode == 0
        mock_run.assert_called_once()

    @patch("rw_blueprint.deployer.targets.run")
    def test_execute_failure(self, mock_run):
        """Test failed command execution."""
        mock_run.return_value = _make_result(returncode=1, stdout="", stderr="Failed")

        manager = TargetManager({"infra": {"host": "100.79.58.118"}})
        result = manager.execute("infra", ["systemctl", "start", "caddy"])

        assert result.success is False
        assert "Failed" in result.stderr
        mock_run.assert_called_once()

    @patch("rw_blueprint.deployer.targets.run")
    def test_execute_with_timeout(self, mock_run):
        """Test command with timeout."""
        mock_run.return_value = _make_result(returncode=0, stdout="ok", stderr="")

        manager = TargetManager({"infra": {"host": "100.79.58.118"}})
        result = manager.execute("infra", ["sleep", "1"], timeout=5)

        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs.get("timeout") == 5

    @patch("rw_blueprint.deployer.targets.run")
    def test_execute_unknown_node(self, mock_run):
        """Test execution on unknown node returns error."""
        manager = TargetManager({"infra": {"host": "100.79.58.118"}})
        result = manager.execute("unknown", ["echo", "test"])

        assert result.success is False
        assert "Unknown node" in result.stderr
        mock_run.assert_not_called()

    @patch("rw_blueprint.deployer.targets.run")
    def test_transfer_file_success(self, mock_run):
        """Test file transfer via scp."""
        mock_run.return_value = _make_result(returncode=0, stdout="", stderr="")

        manager = TargetManager({"infra": {"host": "100.79.58.118"}})
        result = manager.transfer_file("infra", Path("/local/path"), Path("/remote/path"))

        assert result.success is True
        mock_run.assert_called_once()

    @patch("rw_blueprint.deployer.targets.run")
    def test_transfer_file_failure(self, mock_run):
        """Test file transfer failure."""
        mock_run.return_value = _make_result(returncode=1, stdout="", stderr="scp error")

        manager = TargetManager({"infra": {"host": "100.79.58.118"}})
        result = manager.transfer_file("infra", Path("/local/path"), Path("/remote/path"))

        assert result.success is False
        assert "scp error" in result.stderr


class TestRunResult:
    """Test RunResult dataclass."""

    def test_success_result(self):
        """Test success result creation."""
        result = RunResult(success=True, returncode=0, stdout="ok", stderr="")
        assert result.success is True

    def test_failure_result(self):
        """Test failure result creation."""
        result = RunResult(success=False, returncode=1, stdout="", stderr="error")
        assert result.success is False
        assert result.returncode == 1
