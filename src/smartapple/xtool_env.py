"""xtool environment manager for smart-apple-dev.

xtool is a cross-platform Xcode replacement that lets you build, sign, and
install iOS apps from Linux, Windows/WSL, or macOS. It is written in Swift,
so it requires a Swift toolchain on Linux/Windows (Swift for Linux is freely
downloadable from swift.org).

This module provides:
  - `xtool_status()`  - report what's installed
  - `xtool_install()` - download Swift + build xtool from source
  - `xtool_uninstall()` - remove the install

All paths live under `~/.smart-apple-dev/`:
  - swift/   - Swift for Linux toolchain (extracted tarball)
  - xtool/   - xtool source + .build/ artifacts
  - tools/   - symlinks: `swift`, `xtool`, plus existing ldid/ld64.lld

The user can also pre-populate `~/.smart-apple-dev/swift/` themselves and
just run `xtool install` to skip the 600MB download.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tarfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .core.config import get_tool_dir, ensure_dirs, get_platform


# --- Configuration ---

# Latest known-good Swift for Linux (Ubuntu 22.04 base) + the ubuntu2204
# toolchain runs fine on Debian 13 / Parrot because they share the same
# libc6 / libstdc++ ABI.
#
# xtool requires Swift >=6.0 (its Package.swift declares
# `swift-tools-version:6.0`). 6.0.3 is the smallest download that works.
SWIFT_VERSION = "6.1.3"
SWIFT_BASE = f"https://download.swift.org/swift-{SWIFT_VERSION}-release/ubuntu2204"
SWIFT_TARBALL = (
    f"{SWIFT_BASE}/swift-{SWIFT_VERSION}-RELEASE/"
    f"swift-{SWIFT_VERSION}-RELEASE-ubuntu22.04.tar.gz"
)
SWIFT_DIR_NAME = f"swift-{SWIFT_VERSION}-RELEASE-ubuntu22.04"

XTOOL_REPO = "https://github.com/xtool-org/xtool.git"
XTOOL_CLONE_DEPTH = 1
XTOOL_BUILD_PRODUCT = "xtool"
# Build configuration: release builds are ~3x faster at runtime but slower to compile.
XTOOL_BUILD_CONFIG = "release"


# --- Status ---

@dataclass
class XtoolStatus:
    """Snapshot of the xtool environment state."""
    platform: str
    swift_installed: bool = False
    swift_path: str | None = None
    swift_version: str | None = None
    xtool_cloned: bool = False
    xtool_built: bool = False
    xtool_path: str | None = None
    on_path: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "swift_installed": self.swift_installed,
            "swift_path": self.swift_path,
            "swift_version": self.swift_version,
            "xtool_cloned": self.xtool_cloned,
            "xtool_built": self.xtool_built,
            "xtool_path": self.xtool_path,
            "on_path": self.on_path,
            "notes": self.notes,
        }

    def is_ready(self) -> bool:
        """All components installed and on PATH."""
        return self.swift_installed and self.xtool_built and self.on_path


def _install_root() -> Path:
    """Where to install the xtool environment.

    Defaults to `~/.smart-apple-dev/swift/` and `~/.smart-apple-dev/xtool/`
    for discoverability. If the home partition has < 5 GB free and /tmp
    is large (tmpfs or bigger), the install falls back to `/tmp/sad-install/`
    and the symlinks still land in the usual place so the CLI can find them.

    Override with the `SAD_XTOOL_INSTALL_ROOT` env var.
    """
    override = os.environ.get("SAD_XTOOL_INSTALL_ROOT")
    if override:
        return Path(override)
    home_root = Path.home() / ".smart-apple-dev"
    # If home has at least 5 GB free, use it
    try:
        st = os.statvfs(home_root.parent)
        free_gb = (st.f_bavail * st.f_frsize) / (1024 ** 3)
    except Exception:
        free_gb = 0
    if free_gb >= 5:
        return home_root
    # Fall back to /tmp where we usually have more room
    return Path("/tmp") / "sad-install"


def _swift_install_path() -> Path:
    return _install_root() / "swift" / SWIFT_DIR_NAME


def _xtool_install_path() -> Path:
    return _install_root() / "xtool"


def _swift_bin() -> Path | None:
    p = _swift_install_path() / "usr" / "bin" / "swift"
    return p if p.exists() and os.access(p, os.X_OK) else None


def _xtool_bin() -> Path | None:
    p = _xtool_install_path() / ".build" / XTOOL_BUILD_CONFIG / "xtool"
    return p if p.exists() and os.access(p, os.X_OK) else None


def _is_on_path(name: str) -> bool:
    for d in os.environ.get("PATH", "").split(":"):
        c = Path(d) / name
        if c.exists() and os.access(c, os.X_OK):
            return True
    return False


def xtool_status() -> XtoolStatus:
    """Check the current xtool environment state.

    Reports whether Swift for Linux is installed, whether xtool is cloned
    and built, and whether the tools are on PATH.
    """
    s = XtoolStatus(platform=get_platform())

    # Swift
    sb = _swift_bin()
    if sb is not None:
        s.swift_installed = True
        s.swift_path = str(sb)
        try:
            r = subprocess.run([str(sb), "--version"],
                               capture_output=True, text=True, timeout=30)
            ver = (r.stdout or r.stderr).strip().splitlines()[0]
            s.swift_version = ver
        except Exception as e:
            s.notes.append(f"swift --version failed: {e}")
    else:
        # Check if Swift is already on PATH (e.g. user installed via apt)
        for d in os.environ.get("PATH", "").split(":"):
            c = Path(d) / "swift"
            if c.exists() and os.access(c, os.X_OK):
                s.swift_installed = True
                s.swift_path = str(c)
                try:
                    r = subprocess.run([str(c), "--version"],
                                       capture_output=True, text=True, timeout=30)
                    s.swift_version = (r.stdout or r.stderr).strip().splitlines()[0]
                except Exception:
                    pass
                break
        if not s.swift_installed:
            s.notes.append("Swift for Linux not installed; run `smart-apple-dev xtool install`")

    # xtool
    xd = _xtool_install_path()
    if (xd / ".git").exists():
        s.xtool_cloned = True
    xb = _xtool_bin()
    if xb is not None:
        s.xtool_built = True
        s.xtool_path = str(xb)

    # On PATH?
    s.on_path = _is_on_path("xtool") and _is_on_path("swift")

    if s.swift_installed and not s.xtool_built:
        s.notes.append("Swift installed; xtool not built yet. Run `xtool install`.")
    if s.xtool_built and not s.on_path:
        s.notes.append(
            "xtool is built but not on PATH. Add to PATH or use --swift/--xtool flags."
        )
    return s


# --- Install ---

def _run(cmd: list[str], cwd: Path | None = None,
         timeout: int | None = None) -> tuple[int, str, str]:
    """Run a command, return (returncode, stdout, stderr)."""
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout, r.stderr


def _download(url: str, dest: Path, timeout: int = 1800) -> bool:
    """Download url to dest. Returns True on success.

    Prefers `aria2c` (faster, handles reconnects, supports resume) when
    available; falls back to `curl` with retry. Swift.org downloads
    regularly drop the connection on 600 MB files; aria2c handles that
    much better.
    """
    if dest.exists():
        dest.unlink()
    aria2c = shutil.which("aria2c")
    if aria2c:
        r = subprocess.run(
            [aria2c, "-c", "-x", "4", "-s", "4",
             "--max-tries=5", "--retry-wait=3",
             "-d", str(dest.parent), "-o", dest.name, url],
            capture_output=True, text=True, timeout=timeout,
        )
        return r.returncode == 0 and dest.exists()
    # Fallback: curl with retry-connrefused (handles "connection reset by peer")
    r = subprocess.run(
        ["curl", "-fL", "--retry", "10", "--retry-connrefused",
         "--retry-delay", "5", "--max-time", str(timeout),
         "-o", str(dest), url],
        capture_output=True, text=True, timeout=timeout,
    )
    return r.returncode == 0 and dest.exists()


def _ensure_swift_toolchain(redownload: bool = False) -> Path:
    """Download and extract Swift for Linux if not already present.

    Returns the path to the swift toolchain root (e.g. ~/.smart-apple-dev/swift/swift-5.10.1-...).
    """
    swift_dir = _swift_install_path()
    if swift_dir.exists() and (swift_dir / "usr" / "bin" / "swift").exists() and not redownload:
        return swift_dir

    parent = swift_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    tarball = parent / f"{SWIFT_DIR_NAME}.tar.gz"

    if not tarball.exists() or redownload:
        print(f"  downloading Swift {SWIFT_VERSION} (~600 MB)...")
        if not _download(SWIFT_TARBALL, tarball):
            raise RuntimeError(
                f"download failed: {SWIFT_TARBALL}\n"
                f"  you can pre-download it and place it at {tarball}"
            )
    print(f"  extracting {tarball.name}...")
    if swift_dir.exists():
        shutil.rmtree(swift_dir)
    # tarball extracts to a single top-level dir; let tarfile create it
    with tarfile.open(tarball, "r:gz") as t:
        # Safe extraction (Python 3.12+ has a data filter)
        try:
            t.extractall(parent, filter="data")
        except TypeError:
            t.extractall(parent)
    if not swift_dir.exists():
        raise RuntimeError(f"extracted tarball but {swift_dir} not found")
    return swift_dir


def _ensure_xtool_repo() -> Path:
    """Clone xtool if not present. Returns the repo path."""
    xd = _xtool_install_path()
    if (xd / ".git").exists():
        return xd
    if xd.exists():
        shutil.rmtree(xd)
    print(f"  cloning {XTOOL_REPO}...")
    r = subprocess.run(
        ["git", "clone", "--depth", str(XTOOL_CLONE_DEPTH), XTOOL_REPO, str(xd)],
        capture_output=True, text=True, timeout=300,
    )
    if r.returncode != 0:
        raise RuntimeError(f"git clone failed: {r.stderr.strip()}")
    return xd


def _build_xtool(swift_bin: Path, xd: Path) -> Path:
    """Build xtool with the given swift compiler. Returns the binary path.
    
    xtool's default Package.swift pins swift-subprocess 0.5.0 which
    requires Swift 6.2. If we are on Swift 6.1.x, we patch the
    Package.swift to use swift-subprocess 0.4 instead, which is the
    newest version that builds on Swift 6.1.
    """
    # Decide which swift-subprocess version to use based on installed swift
    r = subprocess.run([str(swift_bin), "--version"],
                       capture_output=True, text=True, timeout=10)
    ver_str = (r.stdout or r.stderr).strip().split()[2]  # "Swift version 6.1.3 (...)"
    m = re.match(r"(\d+)\.(\d+)", ver_str)
    if not m:
        raise RuntimeError(f"cannot parse swift version: {ver_str!r}")
    major, minor = int(m.group(1)), int(m.group(2))
    if (major, minor) >= (6, 2):
        subproc_version = "0.5.0"
    elif (major, minor) >= (6, 1):
        subproc_version = "0.4.0"
    else:
        raise RuntimeError(
            f"xtool needs Swift 6.1+. Installed: {ver_str}. "
            f"Run `smart-apple-dev xtool install --redownload` to get a newer Swift."
        )
    
    pkg = xd / "Package.swift"
    if pkg.exists():
        text = pkg.read_text()
        # Match the swift-subprocess package declaration. The default is
        # either of these forms:
        #   .package(url: "...swift-subprocess", from: "0.5.0"),
        #   .package(url: "...swift-subprocess", .upToNextMinor(from: "0.5.0")),
        # We replace both with the simpler `from:` form pointing at the
        # version that matches the installed Swift.
        import re as _re
        SP_URL = "https://github.com/swiftlang/swift-subprocess"
        n = 0
        for pat in [
            r"(\.package\(url:\s*\"" + SP_URL + r"\"\s*,\s*)\.upToNextMinor\(from:\s*\"0\.5\.0\"\)",
            r"(\.package\(url:\s*\"" + SP_URL + r"\"\s*,\s*)from:\s*\"0\.5\.0\"\)",
        ]:
            replacement = chr(92) + "1from: " + chr(34) + subproc_version + chr(34) + ","
            text, k = _re.subn(pat, replacement, text)
            n += k
        if n > 0:
            print("  patched Package.swift to use swift-subprocess " + subproc_version + " (" + str(n) + " replacement" + ("s" if n != 1 else "") + ")")
            pkg.write_text(text)
    
    print(f"  building xtool (this takes ~5 minutes)...")
    cmd = [
        str(swift_bin), "build",
        "--product", XTOOL_BUILD_PRODUCT,
        "-c", XTOOL_BUILD_CONFIG,
    ]
    r = subprocess.run(cmd, cwd=xd, capture_output=True, text=True, timeout=3600)
    if r.returncode != 0:
        raise RuntimeError(
            f"swift build failed:\n{r.stderr[-2000:] if r.stderr else r.stdout[-2000:]}"
        )
    out = xd / ".build" / XTOOL_BUILD_CONFIG / "xtool"
    if not out.exists():
        raise RuntimeError(f"build returned 0 but {out} not found")
    return out


def _symlink_tools() -> None:
    """Expose swift and xtool via the SAD tools dir so they get on PATH automatically.

    Uses ~/.smart-apple-dev/tools/ as the canonical location regardless of
    where the actual install lives (could be /tmp/sad-install on tight-disk
    hosts). The tools dir is also where ld64.lld and ldid already live.
    """
    tools = get_tool_dir()
    tools.mkdir(parents=True, exist_ok=True)
    sb = _swift_bin()
    if sb:
        link = tools / "swift"
        if link.is_symlink() or link.exists():
            if link.is_symlink():
                link.unlink()
        os.symlink(sb, link)
        # Also expose swift driver companion binaries that the Swift package needs
        sb_dir = sb.parent
        for companion in ("swift-frontend", "swift-driver", "swift-package",
                          "swift-build", "swift-test", "swift-run", "swift-format",
                          "swiftc", "clang", "clang++", "lld", "ld.lld", "ld64.lld",
                          "lldb", "docc"):
            c = sb_dir / companion
            if c.exists() and not (tools / companion).exists():
                os.symlink(c, tools / companion)
    xb = _xtool_bin()
    if xb:
        link = tools / "xtool"
        if link.is_symlink() or link.exists():
            if link.is_symlink():
                link.unlink()
        os.symlink(xb, link)


def xtool_install(redownload: bool = False) -> XtoolStatus:
    """Install Swift for Linux and build xtool. Idempotent.

    Steps:
      1. Download Swift for Linux (~600 MB) to ~/.smart-apple-dev/swift/
      2. Extract the tarball
      3. Clone the xtool repo to ~/.smart-apple-dev/xtool/
      4. `swift build` to compile xtool
      5. Symlink `swift` and `xtool` into ~/.smart-apple-dev/tools/
    """
    ensure_dirs()
    print("Installing xtool environment...")
    swift_dir = _ensure_swift_toolchain(redownload=redownload)
    sb = swift_dir / "usr" / "bin" / "swift"
    if not (sb.exists() and os.access(sb, os.X_OK)):
        raise RuntimeError(f"swift not at expected path: {sb}")
    xd = _ensure_xtool_repo()
    _build_xtool(sb, xd)
    _symlink_tools()
    print("xtool install complete.")
    return xtool_status()


def xtool_uninstall() -> None:
    """Remove the xtool environment (Swift toolchain, xtool source, symlinks)."""
    targets = [
        Path.home() / ".smart-apple-dev" / "swift",
        Path.home() / ".smart-apple-dev" / "xtool",
    ]
    for t in targets:
        if t.exists():
            print(f"  removing {t}")
            shutil.rmtree(t)
    # Remove symlinks
    tools = get_tool_dir()
    for name in ("swift", "swift-frontend", "swift-driver", "swift-package",
                 "swift-build", "swift-test", "swift-run", "swift-format", "xtool"):
        link = tools / name
        if link.is_symlink():
            link.unlink()
            print(f"  removed {link}")
