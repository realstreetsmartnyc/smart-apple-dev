"""Rust build backend — wraps cargo + cross-rs."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .orchestrator import BuildResult, run_cmd
from ..core.config import ProjectConfig, check_tool


class RustBackend:
    """Builds Rust apps for iOS using cargo + cross-rs."""

    def __init__(self, config: ProjectConfig):
        self.config = config

    def build(self, config: ProjectConfig, project_dir: Path,
              target: str = "ios", release: bool = False) -> BuildResult:
        """Build a Rust project for iOS."""
        cargo = check_tool("cargo")
        if cargo is None:
            return BuildResult(
                success=False,
                errors=["cargo not found. Install with: curl --proto '=https' "
                        "--tlsv1.2 -sSf https://sh.rustup.rs | sh"],
                language="rust",
            )

        # Determine target triple
        if target in ("ios",):
            target_triple = "aarch64-apple-ios"
        elif target == "ios-simulator":
            target_triple = "x86_64-apple-ios-simulator"
        elif target == "macos":
            target_triple = "aarch64-apple-darwin"
        else:
            target_triple = "aarch64-apple-ios"

        # Check if the target is installed
        if not self.ensure_target(target_triple):
            return BuildResult(
                success=False,
                errors=[f"Rust target {target_triple} not installed. Run: rustup target add {target_triple}" if check_tool("rustup") else "rustup not found. Install with: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"],
                language="rust",
            )

        cmd = [cargo, "build"]
        if release:
            cmd.append("--release")
        cmd.extend(["--target", target_triple])

        exit_code, stdout, stderr = run_cmd(cmd, cwd=project_dir)

        # Find artifact
        artifact = None
        build_dir = project_dir / "target" / target_triple
        if release:
            build_dir = project_dir / "target" / target_triple / "release"
        else:
            build_dir = project_dir / "target" / target_triple / "debug"

        if build_dir.exists():
            for binary in build_dir.rglob(config.name):
                if binary.is_file() and os.access(binary, os.X_OK):
                    artifact = binary
                    break

        return BuildResult(
            success=exit_code == 0,
            output=stdout,
            artifact=artifact,
            errors=[stderr] if stderr and exit_code != 0 else [],
            language="rust",
        )

    def ensure_target(self, target_triple: str) -> bool:
        """Ensure the Rust target is installed."""
        rustup = check_tool("rustup")
        if rustup is None:
            return False
        exit_code, stdout, _ = run_cmd(
            [rustup, "target", "list", "--installed"],
            timeout=30,
        )
        if exit_code != 0:
            return False
        installed = {t.strip() for t in stdout.strip().split("\n") if t.strip()}
        return target_triple in installed