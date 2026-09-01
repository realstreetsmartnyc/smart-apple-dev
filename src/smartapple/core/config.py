"""Core configuration and project management for smart-apple-dev."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib

import yaml


@dataclass
class ProjectConfig:
    """Parsed smartapple.toml configuration."""
    name: str = "my-app"
    language: str = "swift"
    bundle_id: str = "com.example.app"
    version: str = "0.1.0"
    build_system: str = "swiftpm"
    min_os: str = "15.0"
    target: str = "ios"  # ios, macos, catalyst
    signing: dict = field(default_factory=dict)
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: Path) -> "ProjectConfig":
        if not path.exists():
            raise FileNotFoundError(f"Config not found: {path}")
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> "ProjectConfig":
        project = data.get("project", {})
        return cls(
            name=project.get("name", "my-app"),
            language=project.get("language", "swift"),
            bundle_id=project.get("bundle_id", "com.example.app"),
            version=project.get("version", "0.1.0"),
            build_system=project.get("build_system", "swiftpm"),
            min_os=project.get("min_os", "15.0"),
            target=project.get("target", "ios"),
            signing=project.get("signing", {}),
            extra=data,
        )

    def to_toml(self) -> str:
        lines = ["[project]", f'name = "{self.name}"', f'language = "{self.language}"',
                 f'bundle_id = "{self.bundle_id}"', f'version = "{self.version}"',
                 f'build_system = "{self.build_system}"', f'min_os = "{self.min_os}"',
                 f'target = "{self.target}"']
        if self.signing:
            lines.append("")
            lines.append("[signing]")
            for k, v in self.signing.items():
                lines.append(f'{k} = "{v}"')
        return "\n".join(lines) + "\n"


def find_project_root(start: Path | None = None) -> Path | None:
    """Walk up from start to find smartapple.toml."""
    current = (start or Path.cwd()).resolve()
    for parent in [current, *current.parents]:
        if (parent / "smartapple.toml").exists():
            return parent
    return None


def load_config(path: Path | None = None) -> ProjectConfig:
    """Load project config, searching upward if path not given."""
    if path is not None:
        p = Path(path)
        if p.is_dir():
            p = p / "smartapple.toml"
        if not p.exists():
            raise FileNotFoundError(f"smartapple.toml not found at {p}")
        return ProjectConfig.from_file(p)
    root = find_project_root()
    if root is None:
        raise FileNotFoundError("No smartapple.toml found. Run 'smart-apple-dev init' first.")
    return ProjectConfig.from_file(root / "smartapple.toml")


def get_sdk_dir() -> Path:
    """Return the SDK storage directory."""
    home = Path.home()
    sdk = home / ".smart-apple-dev" / "sdk"
    sdk.mkdir(parents=True, exist_ok=True)
    return sdk


def get_tool_dir() -> Path:
    """Return the tool storage directory (xtool, osxcross, etc.)."""
    home = Path.home()
    tool = home / ".smart-apple-dev" / "tools"
    tool.mkdir(parents=True, exist_ok=True)
    return tool


def ensure_dirs() -> dict[str, Path]:
    """Create and return all required directories."""
    home = Path.home()
    base = home / ".smart-apple-dev"
    dirs = {
        "base": base,
        "sdk": base / "sdk",
        "tools": base / "tools",
        "certs": base / "certs",
        "profiles": base / "profiles",
        "build": base / "build",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    return dirs


def check_tool(name: str) -> str | None:
    """Check if a tool binary is available on PATH or in tool dir."""
    tool_dir = get_tool_dir()
    # Check tool dir first
    local = tool_dir / name
    if local.exists() and os.access(local, os.X_OK):
        return str(local)
    # Check PATH
    for p in os.environ.get("PATH", "").split(":"):
        candidate = Path(p) / name
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def get_platform() -> str:
    """Detect current platform."""
    if sys.platform.startswith("linux"):
        return "linux"
    elif sys.platform == "darwin":
        return "macos"
    elif sys.platform in ("win32", "cygwin"):
        return "windows"
    return "unknown"


def get_arch() -> str:
    """Detect current architecture."""
    import platform
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        return "x86_64"
    elif machine in ("aarch64", "arm64"):
        return "arm64"
    return machine