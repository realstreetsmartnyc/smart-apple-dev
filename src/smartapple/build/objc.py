"""Objective-C build backend — delegates to CppBackend for cross-platform builds."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .orchestrator import BuildResult, run_cmd
from ..core.config import ProjectConfig, check_tool


class ObjCBackend:
    """Builds Objective-C apps for iOS/macOS.

    Delegates to CppBackend which handles clang + osxcross toolchain.
    On Linux/Windows without osxcross, falls back to xtool if available.
    """

    def __init__(self, config: ProjectConfig):
        self.config = config

    def build(self, config: ProjectConfig, project_dir: Path,
              target: str = "ios", release: bool = False) -> BuildResult:
        """Build an Objective-C project for iOS/macOS."""
        # Prefer clang + osxcross for ObjC (Swift xtool is for Swift projects).
        # Only fall back to xtool if no clang is available at all.
        clang_path = check_tool("clang")
        if clang_path is None:
            # No clang — try xtool as a last resort
            xtool_path = check_tool("xtool")
            if xtool_path is not None:
                return self._build_with_xtool(xtool_path, config, project_dir, target, release)

        # Try CppBackend which handles clang + osxcross
        try:
            from .cpp import CppBackend
            cpp_backend = CppBackend(config)
            if cpp_backend.is_available():
                # ObjC sources are handled by CppBackend
                return cpp_backend.build(config, project_dir, target, release)
        except ImportError:
            pass

        # No CppBackend and no xtool — try direct clang
        if clang_path is None:
            return BuildResult(
                success=False,
                errors=[
                    "No ObjC build tool found. Options:\n"
                    "  1. Install osxcross + clang: see USER_GUIDE.md\n"
                    "  2. Install xtool: curl -fsSL https://xtool.sh/install.sh | bash"
                ],
                language="objc",
            )
        return self._build_with_clang(clang_path, config, project_dir, target, release)

    def _build_with_xtool(self, xtool_path: str, config: ProjectConfig,
                           project_dir: Path, target: str, release: bool) -> BuildResult:
        """Build using xtool (cross-platform Xcode replacement)."""
        target_triple = self._target_triple(target)
        cmd = [xtool_path, "build"]
        if release:
            cmd.extend(["-c", "release"])
        if target_triple:
            cmd.extend(["--target", target_triple])

        exit_code, stdout, stderr = run_cmd(cmd, cwd=project_dir, timeout=600)
        artifact = self._find_artifact(project_dir, config.name)

        return BuildResult(
            success=exit_code == 0,
            output=stdout,
            artifact=artifact,
            errors=[stderr] if stderr and exit_code != 0 else [],
            language="objc",
        )

    def _build_with_clang(self, clang_path: str, config: ProjectConfig,
                           project_dir: Path, target: str, release: bool) -> BuildResult:
        """Build using clang directly with osxcross SDK."""
        # Collect all .m and .mm files
        sources = list(project_dir.rglob("*.m")) + list(project_dir.rglob("*.mm"))
        if not sources:
            return BuildResult(
                success=False,
                errors=["No .m or .mm files found in project"],
                language="objc",
            )

        # Get SDK path
        sdk_path = self._get_sdk_path(target)
        target_triple = self._target_triple(target)

        # Build output directories
        obj_dir = project_dir / "build" / target / "obj"
        obj_dir.mkdir(parents=True, exist_ok=True)
        bin_dir = project_dir / "build" / target / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)

        # Compile each source
        objects = []
        for src in sources:
            obj_file = obj_dir / (src.stem + ".o")
            cmd = [
                clang_path, "-c", str(src), "-o", str(obj_file),
                "--target=" + target_triple,
                f"-isysroot{sdk_path}",
                "-fobjc-arc",
            ]
            if release:
                cmd.extend(["-O2", "-DNDEBUG"])
            else:
                cmd.extend(["-O0", "-g"])
            exit_code, stdout, stderr = run_cmd(cmd, cwd=project_dir)
            if exit_code != 0:
                return BuildResult(
                    success=False,
                    output=stdout,
                    errors=[f"Compilation failed for {src.name}:\n{stderr}"],
                    language="objc",
                )
            objects.append(obj_file)

        # Link
        binary_name = config.name
        output_path = bin_dir / binary_name
        link_cmd = [
            clang_path,
            *[str(o) for o in objects],
            "-o", str(output_path),
            "--target=" + target_triple,
            f"-isysroot{sdk_path}",
            "-framework", "Foundation",
            "-framework", "UIKit",
            "-framework", "CoreGraphics",
        ]
        exit_code, stdout, stderr = run_cmd(link_cmd, cwd=project_dir)

        return BuildResult(
            success=exit_code == 0,
            output=stdout,
            artifact=output_path if output_path.exists() else None,
            errors=[stderr] if stderr and exit_code != 0 else [],
            language="objc",
        )

    def _target_triple(self, target: str) -> str:
        """Return clang --target string for the platform."""
        mapping = {
            "ios": "arm64-apple-ios",
            "ios-simulator": "arm64-apple-ios-simulator",
            "macos": "arm64-apple-darwin",
        }
        return mapping.get(target, "arm64-apple-ios")

    def _get_sdk_path(self, target: str) -> str:
        """Get the SDK path for the target."""
        from ..core.sdk import get_sdk, SdkError
        platform_map = {
            "ios": "iphoneos",
            "ios-simulator": "iphonesimulator",
            "macos": "macosx",
        }
        platform = platform_map.get(target, "iphoneos")
        try:
            return str(get_sdk(platform))
        except SdkError:
            # Fall back to environment variable
            env_var = f"{platform.upper()}_SDK_PATH"
            return os.environ.get(env_var, "")

    def _find_artifact(self, project_dir: Path, name: str) -> Path | None:
        """Find the built artifact."""
        for build_dir in [project_dir / ".build", project_dir / "build"]:
            if not build_dir.exists():
                continue
            for ext in [".ipa", ".app", ".framework"]:
                for artifact in build_dir.rglob(f"*{ext}"):
                    return artifact
        return None

    def is_available(self) -> bool:
        """Check if ObjC build tools are available."""
        if check_tool("xtool") is not None:
            return True
        try:
            from .cpp import CppBackend
            return CppBackend(ProjectConfig()).is_available()
        except ImportError:
            return check_tool("clang") is not None
