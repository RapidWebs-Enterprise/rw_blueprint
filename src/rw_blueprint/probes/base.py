"""Base classes for probes."""

from __future__ import annotations

import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rw_blueprint.live_state import LiveStateFragment


@dataclass(frozen=True)
class ProbeResult:
    """Result of a probe execution."""

    name: str
    fragment: LiveStateFragment
    errors: list[str]
    duration_ms: int


class Probe(ABC):
    """Abstract base class for all probes."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique probe identifier."""

    @abstractmethod
    def run(self) -> ProbeResult:
        """Execute the probe and return a fragment."""

    def _run_cmd(self, cmd: list[str], timeout: int = 10) -> tuple[int, str, str]:
        """Run a command and return (exit_code, stdout, stderr)."""
        try:
            result = subprocess.run(  # noqa: S603
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"timeout after {timeout}s"
        except FileNotFoundError:
            return -1, "", f"command not found: {cmd[0]}"
        except Exception as e:
            return -1, "", str(e)
