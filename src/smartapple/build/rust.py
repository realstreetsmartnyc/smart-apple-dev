"""Rust build backend — wraps cargo + cross-rs."""

from __future__ import annotations

import os
import plistlib
import shutil
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

        # For Apple targets on Linux: point rustc at our clang + SDK + ld64.lld
        env_overrides = dict(os.environ)
        if target_triple.endswith("-apple-darwin") or target_triple.endswith("-apple-ios"):
            sdk_path = os.environ.get("SDKROOT")
            if sdk_path is None:
                try:
                    from ..core.sdk import list_installed_sdks
                    sdks = list_installed_sdks()
                    for s in sdks:
                        if s.platform == "macosx":
                            sdk_path = str(s.path)
                            break
                except Exception:
                    sdk_path = None
            clang = check_tool("clang")
            ld64 = check_tool("ld64.lld") or check_tool("ld.lld")
            # Determine arch for link args
            arch = "arm64" if "aarch64" in target_triple else "x86_64"
            triple = f"{arch}-apple-darwin" if "darwin" in target_triple else f"{arch}-apple-ios"
            # Build RUSTFLAGS that wire clang as linker and ld64.lld as backend
            rustflags = []
            if sdk_path and clang and ld64:
                ld64_dir = os.path.dirname(ld64)
                rustflags = [
                    f"-Clink-arg=-fuse-ld={ld64}",
                    f"-Clink-arg=-B{ld64_dir}",
                    f"-Clink-arg=--target={triple}",
                    f"-Clink-arg=-isysroot",
                    f"-Clink-arg={sdk_path}",
                    f"-Clink-arg=-mmacosx-version-min=11.0",
                    "-Clink-arg=-Wl,-arch",
                    f"-Clink-arg=-Wl,{arch}",
                    "-Clink-arg=-Wl,-platform_version",
                    "-Clink-arg=-Wl,macos",
                    "-Clink-arg=-Wl,11.0",
                    "-Clink-arg=-Wl,11.3",
                ]
                env_overrides[f"CARGO_TARGET_{target_triple.upper().replace('-','_')}_LINKER"] = clang
            env_key = f"CARGO_TARGET_{target_triple.upper().replace('-','_')}_RUSTFLAGS"
            existing = env_overrides.get(env_key, "")
            if existing:
                rustflags = [existing] + rustflags
            env_overrides[env_key] = " ".join(rustflags)
            if sdk_path:
                env_overrides["SDKROOT"] = sdk_path

        cmd = [cargo, "build"]
        if release:
            cmd.append("--release")
        cmd.extend(["--target", target_triple])

        exit_code, stdout, stderr = run_cmd(cmd, cwd=project_dir, env=env_overrides)

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

        # If building for macOS, wrap the Mach-O binary in a .app bundle
        # so the sign command can find it.
        if exit_code == 0 and artifact and target_triple.endswith("-apple-darwin"):
            try:
                app_dir = project_dir / "build" / "macos" / f"{config.name}.app"
                contents_dir = app_dir / "Contents" / "MacOS"
                contents_dir.mkdir(parents=True, exist_ok=True)
                bundle_bin = contents_dir / config.name
                shutil.copy2(artifact, bundle_bin)
                os.chmod(bundle_bin, 0o755)
                # Write Info.plist
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
            except Exception as e:
                # Non-fatal; signing will fail but the raw binary still exists.
                pass

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