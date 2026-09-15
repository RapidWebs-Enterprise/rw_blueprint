"""Tests for deployment state tracker."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from rw_blueprint.deployer.state import DeploymentRecord, DeploymentState


class TestDeploymentState:
    """Test DeploymentState persistence."""

    def test_record_deployment(self):
        """Test recording a deployment."""
        with TemporaryDirectory() as tmpdir:
            state = DeploymentState(Path(tmpdir))
            record = DeploymentRecord(
                version="1.0.0",
                deployed_at="2026-09-15T10:00:00Z",
                deployed_by="sysop",
                status="healthy",
                image="localhost/caddy:latest",
                config_hash="sha256:abc123",
            )

            state.record("infra", "caddy", record)
            history = state.get_history("infra", "caddy")
            assert len(history) == 1
            assert history[0]["version"] == "1.0.0"

    def test_get_previous_healthy(self):
        """Test getting previous healthy deployment."""
        with TemporaryDirectory() as tmpdir:
            state = DeploymentState(Path(tmpdir))

            # Record a failed deployment
            failed_record = DeploymentRecord(
                version="1.1.0",
                deployed_at="2026-09-15T14:30:00Z",
                deployed_by="automation",
                status="failed",
                image="localhost/caddy:new",
                config_hash="sha256:def456",
            )
            state.record("infra", "caddy", failed_record)

            # Record a healthy deployment
            healthy_record = DeploymentRecord(
                version="1.0.0",
                deployed_at="2026-09-15T10:00:00Z",
                deployed_by="sysop",
                status="healthy",
                image="localhost/caddy:old",
                config_hash="sha256:old",
            )
            state.record("infra", "caddy", healthy_record)

            # Get previous healthy (should find 1.0.0)
            previous = state.get_previous_healthy("infra", "caddy")
            assert previous is not None
            assert previous.version == "1.0.0"

    def test_get_previous_healthy_none(self):
        """Test getting previous healthy when none exists."""
        with TemporaryDirectory() as tmpdir:
            state = DeploymentState(Path(tmpdir))

            # Only record failed deployments
            failed_record = DeploymentRecord(
                version="1.1.0",
                deployed_at="2026-09-15T14:30:00Z",
                deployed_by="automation",
                status="failed",
                image="localhost/caddy:new",
                config_hash="sha256:def456",
            )
            state.record("infra", "caddy", failed_record)

            previous = state.get_previous_healthy("infra", "caddy")
            assert previous is None

    def test_get_history_empty(self):
        """Test getting history for non-existent service."""
        with TemporaryDirectory() as tmpdir:
            state = DeploymentState(Path(tmpdir))
            history = state.get_history("infra", "nonexistent")
            assert history == []

    def test_multiple_deployments(self):
        """Test multiple deployments accumulate."""
        with TemporaryDirectory() as tmpdir:
            state = DeploymentState(Path(tmpdir))

            for i in range(3):
                record = DeploymentRecord(
                    version=f"1.{i}.0",
                    deployed_at=f"2026-09-15T10:0{i}:00Z",
                    deployed_by="sysop",
                    status="healthy",
                    image="localhost/caddy:latest",
                    config_hash=f"sha256:hash{i}",
                )
                state.record("infra", "caddy", record)

            history = state.get_history("infra", "caddy")
            assert len(history) == 3


class TestDeploymentRecord:
    """Test DeploymentRecord dataclass."""

    def test_create_record(self):
        """Test creating a deployment record."""
        record = DeploymentRecord(
            version="1.0.0",
            deployed_at="2026-09-15T10:00:00Z",
            deployed_by="sysop",
            status="healthy",
            image="localhost/caddy:latest",
            config_hash="sha256:abc123",
        )
        assert record.version == "1.0.0"
        assert record.status == "healthy"

    def test_record_serialization(self):
        """Test record serialization to dict."""
        record = DeploymentRecord(
            version="1.0.0",
            deployed_at="2026-09-15T10:00:00Z",
            deployed_by="sysop",
            status="healthy",
            image="localhost/caddy:latest",
            config_hash="sha256:abc123",
        )
        data = record.to_dict()
        assert "version" in data
        assert data["version"] == "1.0.0"

    def test_record_deserialization(self):
        """Test record deserialization from dict."""
        data = {
            "version": "1.0.0",
            "deployed_at": "2026-09-15T10:00:00Z",
            "deployed_by": "sysop",
            "status": "healthy",
            "image": "localhost/caddy:latest",
            "config_hash": "sha256:abc123",
        }
        record = DeploymentRecord.from_dict(data)
        assert record.version == "1.0.0"
        assert record.status == "healthy"
