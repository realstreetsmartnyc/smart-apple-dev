"""Swift/SwiftPM build backend — wraps xtool."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .orchestrator import BuildResult, run_cmd
from ..core.config import ProjectConfig, check_tool, get_tool_dir


class SwiftBackend:
    """Builds Swift/iOS apps using xtool (cross-platform Xcode replacement)."""

    def __init__(self, config: ProjectConfig):
        self.config = config

    def build(self, config: ProjectConfig, project_dir: Path,
              target: str = "ios", release: bool = False) -> BuildResult:
        """Build a SwiftPM project for iOS using xtool."""
        # Check xtool availability
        xtool_path = check_tool("xtool")
        if xtool_path is None:
            return BuildResult(
                success=False,
                errors=["xtool not found. Install with: "
                        "curl -fsSL https://xtool.sh/install.sh | bash"],
                language="swift",
            )

        # Determine target triple
        target_triple = self._target_triple(target)

        # Build command
        cmd = [xtool_path, "build"]
        if release:
            cmd.append("-c")
            cmd.append("release")
        if target_triple:
            cmd.extend(["--target", target_triple])

        cwd = project_dir
        exit_code, stdout, stderr = run_cmd(cmd, cwd=cwd)

        # Find the built .ipa or .app
        artifact = None
        build_dir = project_dir / ".build"
        if build_dir.exists():
            for ipa in build_dir.rglob("*.ipa"):
                artifact = ipa
                break
            if artifact is None:
                for app in build_dir.rglob("*.app"):
                    artifact = app
                    break

        return BuildResult(
            success=exit_code == 0,
            output=stdout,
            artifact=artifact,
            errors=[stderr] if stderr and exit_code != 0 else [],
            language="swift",
        )

    def _target_triple(self, target: str) -> str:
        """Map target name to xtool target triple."""
        mapping = {
            "ios": "ios",
            "ios-simulator": "ios-simulator",
            "macos": "macos",
            "catalyst": "catalyst",
            "watchos": "watchos",
            "tvos": "tvos",
        }
        return mapping.get(target, "ios")

    def is_available(self) -> bool:
        return check_tool("xtool") is not None