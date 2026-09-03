"""smart-apple-dev doctor: diagnose the local toolchain and offer to install missing pieces."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .core.config import check_tool, ensure_dirs, get_tool_dir, get_platform
from .core.sdk import list_installed_sdks


@dataclass
class CheckResult:
    """Result of a single doctor check."""
    name: str
    category: str  # toolchain, sdk, device, agent
    available: bool
    path: str | None = None
    required: bool = False
    install_hint: str = ""
    install_fn: Callable[[], bool] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "available": self.available,
            "path": self.path,
            "required": self.required,
            "install_hint": self.install_hint,
        }


@dataclass
class DoctorReport:
    """Full doctor report."""
    platform: str
    arch: str
    checks: list[CheckResult] = field(default_factory=list)
    sdk_count: int = 0
    device_count: int = 0

    @property
    def missing_required(self) -> list[CheckResult]:
        return [c for c in self.checks if c.required and not c.available]

    @property
    def missing_optional(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.required and not c.available]

    @property
    def all_ok(self) -> bool:
        return not self.missing_required


def _version_of(name: str) -> str:
    """Run `name --version` and return the first line, or empty string."""
    try:
        r = subprocess.run([name, "--version"], capture_output=True, text=True, timeout=5)
        out = (r.stdout or r.stderr).strip().split("\n")[0]
        return out
    except Exception:
        return ""


def run_checks() -> DoctorReport:
    """Run all doctor checks and return a report."""
    p = get_platform()
    arch = platform.machine().lower()

    report = DoctorReport(platform=p, arch=arch)

    # --- System tools (required) ---
    for name in ["clang", "make", "tar", "curl", "git"]:
        path = check_tool(name)
        report.checks.append(CheckResult(
            name=name,
            category="toolchain",
            available=path is not None,
            path=path,
            required=True,
            install_hint=f"Install {name} via your package manager (apt, brew, etc.)",
        ))

    # cmake optional
    path = check_tool("cmake")
    report.checks.append(CheckResult(
        name="cmake",
        category="toolchain",
        available=path is not None,
        path=path,
        required=False,
        install_hint="apt install cmake (recommended for C++ projects)",
    ))

    # --- Apple tools ---
    # xtool: Swift + iOS build on non-Mac
    path = check_tool("xtool")
    report.checks.append(CheckResult(
        name="xtool",
        category="toolchain",
        available=path is not None,
        path=path,
        required=False,
        install_hint="Download from https://xtool.sh (Swift/SwiftPM iOS builds)",
        install_fn=install_xtool,
    ))

    # ldid: codesign replacement
    path = check_tool("ldid")
    report.checks.append(CheckResult(
        name="ldid",
        category="toolchain",
        available=path is not None,
        path=path,
        required=False,
        install_hint="Download from https://github.com/opa334/ldid/releases",
        install_fn=install_ldid,
    ))

    # cctools-port: Apple binutils
    path = check_tool("cctools")
    report.checks.append(CheckResult(
        name="cctools",
        category="toolchain",
        available=path is not None,
        path=path,
        required=False,
        install_hint="Build from https://github.com/tpoechtrager/cctools-port",
        install_fn=install_cctools,
    ))

    # --- Language toolchains ---
    for name in ["swift", "cargo", "rustc", "go", "kotlinc", "kotlin-native"]:
        path = check_tool(name)
        report.checks.append(CheckResult(
            name=name,
            category="language",
            available=path is not None,
            path=path,
            required=False,
            install_hint=f"Install {name}",
        ))

    # --- Device tools ---
    for name in ["idevice_id", "ideviceinfo", "ideviceinstaller", "usbmuxd"]:
        path = check_tool(name)
        report.checks.append(CheckResult(
            name=name,
            category="device",
            available=path is not None,
            path=path,
            required=False,
            install_hint="apt install libimobiledevice usbmuxd",
        ))

    # --- SDKs ---
    sdks = list_installed_sdks()
    report.sdk_count = len(sdks)

    # --- Devices ---
    try:
        from .device import list_devices
        report.device_count = len(list_devices())
    except Exception:
        pass

    return report


def print_report(report: DoctorReport) -> None:
    """Print a human-readable report."""
    from . import ui

    ui.banner("smart-apple-dev doctor")
    ui.info(f"Platform: {report.platform}  /  Arch: {report.arch}")
    print()

    by_category: dict[str, list[CheckResult]] = {}
    for c in report.checks:
        by_category.setdefault(c.category, []).append(c)

    for cat, items in by_category.items():
        ui.info(f"[{cat}]")
        for c in items:
            tag = "" if c.available else (" (REQUIRED)" if c.required else " (optional)")
            ver = _version_of(c.name) if c.available and c.path and c.name in ("clang", "cmake") else ""
            ver_str = f"  {ver}" if ver else ""
            label = f"  {c.name}{tag}{ver_str}"
            if c.available:
                ui.success(label)
            elif c.required:
                ui.error(label)
            else:
                ui.warning(label)
        print()

    ui.summary([
        ("SDKs installed", str(report.sdk_count)),
        ("Devices connected", str(report.device_count)),
    ])

    if report.missing_required:
        ui.error(f"MISSING REQUIRED ({len(report.missing_required)}):")
        for c in report.missing_required:
            ui.error(f"  - {c.name}: {c.install_hint}")
        print()

    if report.missing_optional:
        ui.warning(f"Missing optional ({len(report.missing_optional)}):")
        for c in report.missing_optional[:5]:
            ui.info(f"  - {c.name}: {c.install_hint}")
        if len(report.missing_optional) > 5:
            ui.info(f"  ... and {len(report.missing_optional) - 5} more")
        ui.hint("Run `smart-apple-dev doctor --install` to auto-install what we can.")


# ============================================================
# Auto-installers
# ============================================================

# These are best-effort. They only work on Linux x86_64 / arm64 with internet.
# On macOS we don't need them (xcode provides everything).
# On Windows, the user should use WSL2.

XTOOL_VERSION = "1.17"
XTOOL_URLS = {
    "x86_64": f"https://github.com/xtool-org/xtool/releases/download/v{XTOOL_VERSION}/xtool-{XTOOL_VERSION}-linux-x86_64.tar.xz",
    "arm64":  f"https://github.com/xtool-org/xtool/releases/download/v{XTOOL_VERSION}/xtool-{XTOOL_VERSION}-linux-aarch64.tar.xz",
}

# ldid doesn't have official Linux binaries. The Mac binary is on GitHub releases.
# For Linux, we use cctools-port's ld_classic or sign with our own minimal signer.
# Or: download the Mac binary, run it on macOS, or build from source.
LDID_LINUX_BUILD_INSTRUCTIONS = (
    "git clone https://github.com/saurik/ldid.git && cd ldid && "
    "g++ -I . -o ldid ldid.cpp util.cpp -lcrypto -lpthread"
)

# cctools-port is built from source - too heavy for auto-install. Provide instructions only.


def _download_to(url: str, dest: Path, mode: int = 0o755) -> bool:
    """Download a file with curl."""
    try:
        r = subprocess.run(
            ["curl", "-fsSL", "-o", str(dest), url],
            capture_output=True, text=True, timeout=120,
        )
        if r.returncode != 0:
            print(f"    download failed: {r.stderr[:200]}")
            return False
        os.chmod(dest, mode)
        return True
    except Exception as e:
        print(f"    download error: {e}")
        return False


def install_xtool() -> bool:
    """Download and install xtool binary."""
    arch = platform.machine().lower()
    if arch not in XTOOL_URLS:
        print(f"    xtool: no binary for arch {arch}")
        return False

    tools = get_tool_dir()
    url = XTOOL_URLS[arch]
    tarball = tools / f"xtool-{XTOOL_VERSION}.tar.xz"
    print(f"    downloading xtool v{XTOOL_VERSION} for {arch}...")
    if not _download_to(url, tarball):
        return False

    # Extract
    import tarfile
    try:
        with tarfile.open(tarball, "r:xz") as t:
            t.extractall(tools)
        tarball.unlink()
    except Exception as e:
        print(f"    extract failed: {e}")
        return False

    # Find the xtool binary inside
    candidates = list(tools.rglob("xtool"))
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            print(f"    installed: {c}")
            return True

    # If not executable, make it so
    for c in candidates:
        if c.is_file():
            os.chmod(c, 0o755)
            if os.access(c, os.X_OK):
                print(f"    installed: {c}")
                return True

    print(f"    could not find xtool binary in extracted archive")
    return False


def install_ldid() -> bool:
    """ldid auto-install isn't available on Linux (only Mac binary exists).
    Provide build instructions instead.
    """
    print("    No prebuilt Linux ldid binary exists.")
    print(f"    To build from source:")
    print(f"      {LDID_LINUX_BUILD_INSTRUCTIONS}")
    print(f"      cp ldid ~/.smart-apple-dev/tools/ldid")
    print()
    print(f"    Alternative: use cctools-port's codesign instead.")
    return False


def install_cctools() -> bool:
    """cctools-port requires building from source. Provide instructions."""
    print("    cctools-port must be built from source:")
    print("      git clone https://github.com/tpoechtrager/cctools-port")
    print("      cd cctools-port/cctools")
    print("      ./configure --prefix=$HOME/.smart-apple-dev/tools --target=arm64-apple-ios,x86_64-apple-ios,aarch64-apple-darwin")
    print("      make && make install")
    print("      export PATH=$HOME/.smart-apple-dev/tools/bin:$PATH")
    print()
    print("    Alternatively, run smart-apple-dev build --provider cloud for now.")
    return False


def install_all(report: DoctorReport) -> int:
    """Install all auto-installable tools. Returns count of successful installs."""
    ensure_dirs()
    success = 0
    for c in report.checks:
        if c.available or c.install_fn is None:
            continue
        print(f"Installing {c.name}...")
        try:
            if c.install_fn():
                success += 1
        except Exception as e:
            print(f"  failed: {e}")
    return success
