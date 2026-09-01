"""Kotlin/Native build backend."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .orchestrator import BuildResult, run_cmd
from ..core.config import ProjectConfig, check_tool


class KotlinBackend:
    """Builds Kotlin/Native apps for iOS."""

    def __init__(self, config: ProjectConfig):
        self.config = config

    def build(self, config: ProjectConfig, project_dir: Path,
              target: str = "ios", release: bool = False) -> BuildResult:
        """Build a Kotlin/Native project for iOS."""
        # Check for Gradle
        gradlew = project_dir / "gradlew"
        if not gradlew.exists():
            return BuildResult(
                success=False,
                errors=["gradlew not found. Is this a Kotlin/Native project?"],
                language="kotlin",
            )

        # Determine target
        if target in ("ios",):
            kotlin_target = "iosArm64"
        elif target == "ios-simulator":
            kotlin_target = "iosX64"
        elif target == "macos":
            kotlin_target = "macosArm64"
        else:
            kotlin_target = "iosArm64"

        cmd = ["./gradlew", "binaries", f"--target", kotlin_target]
        if release:
            cmd.append("-P")
            cmd.append("kotlin.binary.release=true")

        exit_code, stdout, stderr = run_cmd(cmd, cwd=project_dir, timeout=600)

        # Find artifact
        artifact = None
        build_dir = project_dir / "build" / "binaries"
        if build_dir.exists():
            for binary in build_dir.rglob(f"{config.name}*.kexe"):
                artifact = binary
                break
            if artifact is None:
                for binary in build_dir.rglob(f"{config.name}*.framework"):
                    artifact = binary
                    break

        return BuildResult(
            success=exit_code == 0,
            output=stdout,
            artifact=artifact,
            errors=[stderr] if stderr and exit_code != 0 else [],
            language="kotlin",
        )