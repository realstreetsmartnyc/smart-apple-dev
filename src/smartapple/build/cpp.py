"""C/C++/ObjC build backend — wraps osxcross and clang with LLD for linking."""

from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
from pathlib import Path

from .orchestrator import BuildResult, run_cmd
from ..core.config import ProjectConfig, check_tool, get_tool_dir
from ..core.sdk import SdkError, get_sdk


def _find_mach_o_linker() -> str | None:
    """Find ld64.lld (LLVM's Mach-O linker) anywhere on disk."""
    # Standard names clang accepts
    for name in ("ld64.lld", "ld.lld", "lld"):
        p = check_tool(name)
        if p is not None:
            return p

    # Search well-known LLVM directories for the versioned binaries
    candidates = [
        "/usr/bin/ld64.lld-19", "/usr/bin/ld64.lld-18", "/usr/bin/ld64.lld-17",
        "/usr/bin/ld64.lld-16", "/usr/bin/ld64.lld-15",
        "/usr/bin/ld64.lld", "/usr/bin/lld-19", "/usr/bin/lld-18",
        "/usr/bin/lld-17", "/usr/bin/lld-16", "/usr/bin/lld-15",
        "/usr/bin/lld",
    ]
    for c in candidates:
        if os.path.exists(c) and os.access(c, os.X_OK):
            return c

    # Last resort: PATH search
    import shutil as _shutil
    return _shutil.which("ld64.lld") or _shutil.which("lld")


def _mach_o_arch_for_target(target: str, host_arch: str) -> str:
    """Pick a Mach-O architecture for the given target."""
    if target == "ios":
        return "arm64"  # iOS device is arm64
    if target == "ios-simulator":
        # arm64 simulator on Apple Silicon, x86_64 elsewhere
        return "arm64" if host_arch == "arm64" else "x86_64"
    if target in ("watchos", "tvos"):
        return "arm64"
    # macos / catalyst
    return "arm64" if host_arch == "arm64" else "x86_64"


def _mach_o_target_for(arch: str, sdk_platform: str, min_os: str) -> str:
    """Return the clang --target= string for a Mach-O target."""
    if sdk_platform == "macosx":
        return f"{arch}-apple-darwin{min_os}"
    if sdk_platform == "iphoneos":
        return f"{arch}-apple-ios{min_os}"
    if sdk_platform == "iphonesimulator":
        return f"{arch}-apple-ios{min_os}-simulator"
    # default
    return f"{arch}-apple-darwin{min_os}"


def _is_objc_source(path: Path) -> bool:
    return path.suffix in (".m", ".mm")


def _is_swift_source(path: Path) -> bool:
    return path.suffix == ".swift"


def _is_cpp_source(path: Path) -> bool:
    return path.suffix in (".cpp", ".cc", ".cxx", ".C")


def _is_c_source(path: Path) -> bool:
    return path.suffix == ".c"


class CppBackend:
    """Builds C/C++/Objective-C apps for Apple platforms.

    Requires:
    - clang (any recent LLVM)
    - ld64.lld (LLVM Mach-O linker) OR cctools-port
    - An installed Apple SDK (iPhoneOS or MacOSX) in ~/.smart-apple-dev/sdk/
    """

    def __init__(self, config: ProjectConfig):
        self.config = config

    def is_available(self) -> bool:
        return check_tool("clang") is not None and _find_mach_o_linker() is not None

    def build(self, config: ProjectConfig, project_dir: Path,
              target: str = "ios", release: bool = False) -> BuildResult:
        """Build a C/C++/ObjC project for the given Apple target."""
        # 1. Verify clang
        clang = check_tool("clang")
        if clang is None:
            return BuildResult(
                success=False,
                errors=["clang not found. Install: apt install clang"],
                language=config.language,
            )

        # 2. Verify a Mach-O linker
        linker = _find_mach_o_linker()
        if linker is None:
            return BuildResult(
                success=False,
                errors=[
                    "No Mach-O linker found. Need ld64.lld (LLVM) or cctools-port.",
                    "On Debian/Ubuntu: apt install lld",
                    "Or build cctools-port: https://github.com/tpoechtrager/cctools-port",
                ],
                language=config.language,
            )

        # 3. Get the right SDK
        try:
            if target in ("ios", "ios-simulator"):
                sdk_platform = "iphonesimulator" if target == "ios-simulator" else "iphoneos"
                sdk_path = get_sdk(sdk_platform)
            else:
                sdk_platform = "macosx"
                sdk_path = get_sdk("macosx")
        except SdkError as e:
            return BuildResult(
                success=False,
                errors=[
                    str(e),
                    "",
                    f"To install an {sdk_platform} SDK:",
                    "  On macOS: smart-apple-dev sdk extract (one-time setup)",
                    "  Then move the tarball to Linux and: smart-apple-dev sdk install",
                    "  Community MacOSX mirror: see sdk_install help",
                ],
                language=config.language,
            )

        # 4. Find source files
        sources = sorted([
            p for p in project_dir.iterdir()
            if p.is_file() and (
                _is_c_source(p) or _is_cpp_source(p) or
                _is_objc_source(p) or _is_swift_source(p)
            )
        ])

        # 5. Pick architecture
        from ..core.config import get_arch
        host_arch = get_arch()
        arch = _mach_o_arch_for_target(target, host_arch)

        # 6. Compute clang flags
        min_os = config.min_os
        clang_target = _mach_o_target_for(arch, sdk_platform, min_os)

        cflags = [
            f"--target={clang_target}",
            "-isysroot", str(sdk_path),
            "-fuse-ld=lld",  # clang accepts this; uses the ld64.lld on PATH
            "-fobjc-arc",
        ]
        if release:
            cflags.extend(["-O3", "-DNDEBUG"])
        else:
            cflags.extend(["-O0", "-g"])

        # 7. Decide output structure: macos -> .app, ios -> .app
        bundle_id = config.bundle_id
        name = config.name
        out_dir = project_dir / "build" / target
        out_dir.mkdir(parents=True, exist_ok=True)

        if target.startswith("ios") or target in ("catalyst",):
            # iOS .app: Payload-style root for iOS, but for direct builds we use the bare .app
            binary_dir = out_dir / f"{name}.app"
        else:
            # macOS .app: standard Contents/MacOS/ structure
            binary_dir = out_dir / f"{name}.app" / "Contents" / "MacOS"

        binary_dir.mkdir(parents=True, exist_ok=True)
        binary_path = binary_dir / name

        # 8. Build the compile command
        cmd = [clang] + cflags + [
            "-o", str(binary_path),
        ]
        # Link against Foundation (and UIKit for iOS)
        if sdk_platform == "macosx":
            cmd.extend(["-framework", "Foundation"])
        else:
            cmd.extend(["-framework", "Foundation", "-framework", "UIKit"])

        # C++ sources need the LLVM libc++ runtime
        has_cpp = any(_is_cpp_source(s) for s in sources)
        if has_cpp:
            cmd.extend(["-stdlib=libc++", "-lc++", "-lc++abi"])
            # The libc++ headers are in the SDK; ensure they're found
            sdk_path_str = str(sdk_path)
            # libc++abi lives under usr/lib in the SDK
            libcxx_abi = Path(sdk_path_str) / "usr" / "lib" / "libc++abi.tbd"
            if libcxx_abi.exists():
                cmd.extend(["-L", str(Path(sdk_path_str) / "usr" / "lib")])

        if sources:
            cmd.extend([str(s) for s in sources])
        else:
            return BuildResult(
                success=False,
                errors=[f"No C/ObjC/C++/Swift source files found in {project_dir}"],
                language=config.language,
            )

        # 9. Run the build
        exit_code, stdout, stderr = run_cmd(cmd, cwd=project_dir, timeout=180)

        if exit_code != 0:
            return BuildResult(
                success=False,
                output=stdout,
                errors=[stderr] if stderr else ["Compile failed"],
                language=config.language,
            )

        if not binary_path.exists():
            return BuildResult(
                success=False,
                output=stdout,
                errors=[f"Build reported success but {binary_path} not found"],
                language=config.language,
            )

        # 10. Make binary executable
        os.chmod(binary_path, 0o755)

        # 11. Wrap in .app bundle structure
        app_root = out_dir / f"{name}.app"
        self._write_info_plist(app_root, name, bundle_id, config.version, sdk_platform, min_os)
        self._write_pkginfo(app_root)

        # 12. Verify the result
        verification = self._verify_macho(binary_path)
        if not verification["valid"]:
            return BuildResult(
                success=False,
                errors=[f"Build produced a file but it's not a valid Mach-O: {verification}"],
                language=config.language,
            )

        return BuildResult(
            success=True,
            output=stdout,
            artifact=app_root,
            errors=[],
            language=config.language,
        )

    def _write_info_plist(self, app_root: Path, name: str, bundle_id: str,
                          version: str, sdk_platform: str, min_os: str) -> None:
        """Write Info.plist for the .app bundle."""
        if sdk_platform == "macosx":
            plist_dir = app_root / "Contents"
            plist_path = plist_dir / "Info.plist"
            plist_dir.mkdir(parents=True, exist_ok=True)
            keys = {
                "CFBundleDevelopmentRegion": "en",
                "CFBundleExecutable": name,
                "CFBundleIdentifier": bundle_id,
                "CFBundleInfoDictionaryVersion": "6.0",
                "CFBundleName": name,
                "CFBundleDisplayName": name,
                "CFBundlePackageType": "APPL",
                "CFBundleShortVersionString": version,
                "CFBundleVersion": "1",
                "LSMinimumSystemVersion": min_os,
                "NSHighResolutionCapable": True,
                "NSPrincipalClass": "NSApplication",
            }
        else:
            plist_dir = app_root
            plist_path = plist_dir / "Info.plist"
            keys = {
                "CFBundleDevelopmentRegion": "en",
                "CFBundleExecutable": name,
                "CFBundleIdentifier": bundle_id,
                "CFBundleInfoDictionaryVersion": "6.0",
                "CFBundleName": name,
                "CFBundleDisplayName": name,
                "CFBundlePackageType": "APPL",
                "CFBundleShortVersionString": version,
                "CFBundleVersion": "1",
                "MinimumOSVersion": min_os,
                "UIDeviceFamily": [1, 2],
                "LSRequiresIPhoneOS": True,
            }
        with open(plist_path, "wb") as f:
            plistlib.dump(keys, f)

    def _write_pkginfo(self, app_root: Path) -> None:
        """Write PkgInfo file (8 bytes: 'APPL????')."""
        for p in [
            app_root / "Contents" / "PkgInfo",
            app_root / "PkgInfo",
        ]:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"APPL????")

    def _verify_macho(self, path: Path) -> dict:
        """Verify the file is a valid Mach-O executable."""
        try:
            data = path.read_bytes()
        except Exception as e:
            return {"valid": False, "error": str(e)}

        if len(data) < 4:
            return {"valid": False, "error": "file too small"}

        magic = data[:4]
        if magic in (b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf",
                     b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xce",
                     b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca"):
            # Determine arch from magic
            if magic in (b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf"):
                arch = "64-bit"
            elif magic in (b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xce"):
                arch = "32-bit"
            else:
                arch = "fat"
            return {"valid": True, "format": "Mach-O", "arch": arch, "size": len(data)}

        if data[:4] == b"\x7fELF":
            return {"valid": False, "error": "ELF (Linux), not Mach-O"}

        return {"valid": False, "error": f"unknown magic: {magic.hex()}"}
