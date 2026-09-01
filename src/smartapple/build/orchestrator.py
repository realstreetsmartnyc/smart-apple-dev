"""Build orchestration — dispatches to language-specific backends."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..core.config import ProjectConfig, check_tool, get_tool_dir, get_platform
from ..core.sdk import get_sdk


@dataclass
class BuildResult:
    """Result of a build operation."""
    success: bool
    output: str = ""
    artifact: Path | None = None
    errors: list[str] = field(default_factory=list)
    language: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "artifact": str(self.artifact) if self.artifact else None,
            "errors": self.errors,
            "language": self.language,
        }


def run_cmd(cmd: list[str], cwd: Path | None = None,
            env: dict | None = None, timeout: int = 300) -> tuple[int, str, str]:
    """Run a command and return (exit_code, stdout, stderr)."""
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    try:
        result = subprocess.run(
            cmd, cwd=cwd, env=run_env,
            capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except FileNotFoundError:
        return -1, "", f"Command not found: {cmd[0]}"


class BuildOrchestrator:
    """Dispatches build commands to language-specific backends."""

    def __init__(self, project_dir: Path | None = None):
        self.project_dir = project_dir or Path.cwd()
        self.config: ProjectConfig | None = None

    def load_config(self) -> ProjectConfig:
        from ..core.config import load_config
        self.config = load_config(self.project_dir)
        return self.config

    def build(self, config: ProjectConfig | None = None,
              target: str = "ios", release: bool = False) -> BuildResult:
        """Build the project for the given target."""
        cfg = config or self.config or self.load_config()
        self.config = cfg

        backend_name = self._get_backend(cfg.language)
        backend = self._create_backend(backend_name, cfg)

        if backend is None:
            return BuildResult(
                success=False,
                errors=[f"No backend for language: {cfg.language}"],
                language=cfg.language,
            )

        return backend.build(cfg, self.project_dir, target, release)

    def _get_backend(self, language: str) -> str:
        """Map language name to backend name."""
        mapping = {
            "swift": "swift",
            "swiftui": "swift",
            "objc": "objc",
            "objective-c": "objc",
            "objective_c": "objc",
            "c": "cpp",
            "c++": "cpp",
            "cpp": "cpp",
            "rust": "rust",
            "go": "go",
            "kotlin": "kotlin",
        }
        return mapping.get(language.lower(), language.lower())

    def _create_backend(self, name: str, config: ProjectConfig):
        """Create a backend instance by name."""
        from .swift import SwiftBackend
        from .cpp import CppBackend
        from .rust import RustBackend
        from .go import GoBackend
        from .kotlin import KotlinBackend

        backends = {
            "swift": SwiftBackend,
            "objc": CppBackend,
            "cpp": CppBackend,
            "rust": RustBackend,
            "go": GoBackend,
            "kotlin": KotlinBackend,
        }
        cls = backends.get(name)
        if cls is None:
            return None
        return cls(config)

    def list_backends(self) -> list[str]:
        """List available backend names."""
        return ["swift", "objc", "cpp", "rust", "go", "kotlin"]

    def check_backend_availability(self, language: str) -> dict[str, Any]:
        """Check if a backend is available on this system."""
        backend_name = self._get_backend(language)
        checks = self._backend_checks(backend_name)
        result = {"language": language, "backend": backend_name, "checks": {}}
        for name, cmd in checks.items():
            found = check_tool(cmd[0])
            result["checks"][name] = {
                "available": found is not None,
                "path": found,
                "command": cmd[0],
            }
        return result

    def _backend_checks(self, backend: str) -> dict[str, list[str]]:
        """Return tool checks for a backend."""
        return {
            "swift": {"xtool": ["xtool"], "swift": ["swift"]},
            "objc": {"clang": ["clang"], "osxcross": ["osxcross"]},
            "cpp": {"clang": ["clang"], "osxcross": ["osxcross"], "cmake": ["cmake"]},
            "rust": {"cargo": ["cargo"], "rustc": ["rustc"]},
            "go": {"go": ["go"]},
            "kotlin": {"kotlin": ["kotlinc", "kotlin-native"]},
        }.get(backend, {})