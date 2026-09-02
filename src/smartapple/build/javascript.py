"""JavaScript/TypeScript build backend — wraps npm/yarn + React Native + Expo."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .orchestrator import BuildResult, run_cmd
from ..core.config import ProjectConfig, check_tool


class JavaScriptBackend:
    """Builds JavaScript/TypeScript apps for iOS/macOS using React Native or Expo."""

    def __init__(self, config: ProjectConfig):
        self.config = config

    def build(self, config: ProjectConfig, project_dir: Path,
              target: str = "ios", release: bool = False) -> BuildResult:
        """Build a JavaScript/TypeScript project for the given target."""
        # Check for node/npm
        node = check_tool("node")
        if node is None:
            return BuildResult(
                success=False,
                errors=["node not found. Install from https://nodejs.org/"],
                language="javascript",
            )

        npm = check_tool("npm")
        if npm is None:
            return BuildResult(
                success=False,
                errors=["npm not found. Install Node.js from https://nodejs.org/"],
                language="javascript",
            )

        # Determine build target
        if target in ("ios", "ios-simulator", "macos"):
            return self._build_for_apple_platform(config, project_dir, target, release)

        return self._build_web(config, project_dir, target, release)

    def _build_for_apple_platform(self, config: ProjectConfig, project_dir: Path,
                                   target: str, release: bool) -> BuildResult:
        """Build JavaScript for Apple platforms."""
        # Check for React Native
        rn_cli = check_tool("npx")
        if rn_cli is not None:
            # Check if react-native is installed
            exit_code, stdout, _ = run_cmd(
                ["npx", "--no-install", "react-native", "--version"],
                cwd=project_dir, timeout=30
            )
            if exit_code == 0:
                return self._build_with_react_native(config, project_dir, target, release)

        # Check for Expo
        expo = check_tool("expo")
        if expo is None:
            # Check if expo is available via npx
            exit_code, _, _ = run_cmd(
                ["npx", "--no-install", "expo", "--version"],
                cwd=project_dir, timeout=30
            )
            if exit_code == 0:
                return self._build_with_expo(config, project_dir, target, release)

        # Check for Capacitor
        capacitor = check_tool("npx")
        if capacitor is not None:
            exit_code, _, _ = run_cmd(
                ["npx", "--no-install", "cap", "--version"],
                cwd=project_dir, timeout=30
            )
            if exit_code == 0:
                return self._build_with_capacitor(config, project_dir, target, release)

        # Fallback: Just bundle with webpack/rollup
        return self._build_with_bundler(config, project_dir, target, release)

    def _build_with_react_native(self, config: ProjectConfig, project_dir: Path,
                                   target: str, release: bool) -> BuildResult:
        """Build using React Native CLI."""
        rn_target = "ios" if target in ("ios", "ios-simulator") else "macos"
        if rn_target == "ios" and target == "ios-simulator":
            rn_target = "ios"  # RN handles simulator vs device differently

        cmd = ["npx", "react-native", "run-" + rn_target]
        if release:
            cmd.append("--configuration=Release")

        exit_code, stdout, stderr = run_cmd(cmd, cwd=project_dir, timeout=1200)

        # Look for the .app/.ipa in common locations
        ios_dir = project_dir / "ios"
        if ios_dir.exists():
            build_dir = ios_dir / "build" / "DerivedData"
            if build_dir.exists():
                for ipa in build_dir.rglob("*.ipa"):
                    return BuildResult(
                        success=True,
                        output=stdout,
                        artifact=ipa,
                        errors=[],
                        language="javascript",
                        metadata={"framework": "react-native", "target": target},
                    )

        return BuildResult(
            success=exit_code == 0,
            output=stdout,
            errors=[stderr] if stderr and exit_code != 0 else [],
            language="javascript",
            metadata={"framework": "react-native", "target": target},
        )

    def _build_with_expo(self, config: ProjectConfig, project_dir: Path,
                          target: str, release: bool) -> BuildResult:
        """Build using Expo."""
        if release:
            # For release builds, use EAS Build
            eas = check_tool("eas")
            if eas is not None:
                cmd = ["eas", "build", "--platform", target]
            else:
                # Fall back to expo build
                expo_platform = "ios" if target in ("ios", "ios-simulator") else "ios"
                cmd = ["npx", "expo", "build:" + expo_platform]
                if release:
                    cmd.append("--release-channel")
                    cmd.append("production")
        else:
            # Development build
            if target in ("ios", "ios-simulator"):
                cmd = ["npx", "expo", "run:ios"]
            else:
                cmd = ["npx", "expo", "run:macos"]

        exit_code, stdout, stderr = run_cmd(cmd, cwd=project_dir, timeout=1200)

        return BuildResult(
            success=exit_code == 0,
            output=stdout,
            errors=[stderr] if stderr and exit_code != 0 else [],
            language="javascript",
            metadata={"framework": "expo", "target": target},
        )

    def _build_with_capacitor(self, config: ProjectConfig, project_dir: Path,
                                target: str, release: bool) -> BuildResult:
        """Build using Capacitor."""
        # First build web assets
        cmd = ["npx", "cap", "copy"]
        exit_code, stdout, stderr = run_cmd(cmd, cwd=project_dir, timeout=300)

        if exit_code != 0:
            return BuildResult(
                success=False,
                output=stdout,
                errors=[f"Capacitor copy failed: {stderr}"],
                language="javascript",
            )

        # Sync to native projects
        sync_cmd = ["npx", "cap", "sync", "ios" if target in ("ios", "ios-simulator") else "macos"]
        exit_code, stdout, stderr = run_cmd(sync_cmd, cwd=project_dir, timeout=300)

        return BuildResult(
            success=exit_code == 0,
            output=stdout,
            errors=[stderr] if stderr and exit_code != 0 else [],
            language="javascript",
            metadata={"framework": "capacitor", "target": target},
        )

    def _build_web(self, config: ProjectConfig, project_dir: Path,
                    target: str, release: bool) -> BuildResult:
        """Build as a Progressive Web App."""
        package_json = project_dir / "package.json"
        if not package_json.exists():
            return BuildResult(
                success=False,
                errors=["package.json not found. Initialize with: npm init"],
                language="javascript",
            )

        # Read build script from package.json
        import json
        with open(package_json) as f:
            pkg = json.load(f)

        build_script = pkg.get("scripts", {}).get("build", "webpack --mode production")

        if not release:
            build_script = pkg.get("scripts", {}).get("build:dev", build_script.replace("production", "development"))

        exit_code, stdout, stderr = run_cmd(
            ["npm", "run", build_script.split()[-1] if " " in build_script else "build"],
            cwd=project_dir, timeout=600
        )

        dist_dir = project_dir / "dist"
        if dist_dir.exists():
            return BuildResult(
                success=True,
                output=stdout,
                artifact=dist_dir,
                errors=[],
                language="javascript",
                metadata={"framework": "web", "target": "pwa"},
            )

        return BuildResult(
            success=exit_code == 0,
            output=stdout,
            errors=[stderr] if stderr and exit_code != 0 else [],
            language="javascript",
        )


# Factory function for orchestrator
def create_javascript_backend(config: ProjectConfig) -> JavaScriptBackend:
    return JavaScriptBackend(config)