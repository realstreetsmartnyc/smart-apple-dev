"""Go build backend — native cross-compilation."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .orchestrator import BuildResult, run_cmd
from ..core.config import ProjectConfig, check_tool


class GoBackend:
    """Builds Go apps for iOS/macOS via native cross-compilation."""

    def __init__(self, config: ProjectConfig):
        self.config = config

    def build(self, config: ProjectConfig, project_dir: Path,
              target: str = "ios", release: bool = False) -> BuildResult:
        """Build a Go project for iOS."""
        go_bin = check_tool("go")
        if go_bin is None:
            return BuildResult(
                success=False,
                errors=["Go not found. Install from https://go.dev/dl/"],
                language="go",
            )

        # Determine GOOS/GOARCH
        if target in ("ios",):
            goos = "ios"
            goarch = "arm64"
        elif target == "ios-simulator":
            goos = "ios"
            goarch = "amd64"
        elif target == "macos":
            goos = "darwin"
            goarch = "arm64"
        else:
            goos = "ios"
            goarch = "arm64"

        env = {
            "GOOS": goos,
            "GOARCH": goarch,
            "CGO_ENABLED": "0",  # No CGo for simplicity
        }

        # Build
        cmd = [go_bin, "build", "-o", str(project_dir / "build" / target / config.name)]
        if release:
            cmd.append("-ldflags=-s -w")
        exit_code, stdout, stderr = run_cmd(cmd, cwd=project_dir, env=env)

        artifact = project_dir / "build" / target / config.name
        if not artifact.exists():
            artifact = None

        return BuildResult(
            success=exit_code == 0,
            output=stdout,
            artifact=artifact,
            errors=[stderr] if stderr and exit_code != 0 else [],
            language="go",
        )