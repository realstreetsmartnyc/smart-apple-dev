"""Go build backend — native cross-compilation."""

from __future__ import annotations

import os
import plistlib
import shutil
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

        # Wrap raw Mach-O binary in a .app bundle for macOS targets
        if exit_code == 0 and artifact and artifact.is_file() and goos == "darwin":
            try:
                app_dir = project_dir / "build" / target / f"{config.name}.app"
                contents_dir = app_dir / "Contents" / "MacOS"
                contents_dir.mkdir(parents=True, exist_ok=True)
                bundle_bin = contents_dir / config.name
                shutil.copy2(artifact, bundle_bin)
                os.chmod(bundle_bin, 0o755)
                plist = {
                    "CFBundleDevelopmentRegion": "en",
                    "CFBundleExecutable": config.name,
                    "CFBundleIdentifier": config.bundle_id,
                    "CFBundleInfoDictionaryVersion": "6.0",
                    "CFBundleName": config.name,
                    "CFBundleDisplayName": config.name,
                    "CFBundlePackageType": "APPL",
                    "CFBundleShortVersionString": config.version,
                    "CFBundleVersion": "1",
                    "LSMinimumSystemVersion": "11.0",
                    "NSHighResolutionCapable": True,
                    "NSPrincipalClass": "NSApplication",
                }
                with open(app_dir / "Contents" / "Info.plist", "wb") as fp:
                    plistlib.dump(plist, fp)
                (app_dir / "Contents" / "PkgInfo").write_bytes(b"APPL????")
                artifact = app_dir
            except Exception:
                pass

        return BuildResult(
            success=exit_code == 0,
            output=stdout,
            artifact=artifact,
            errors=[stderr] if stderr and exit_code != 0 else [],
            language="go",
        )