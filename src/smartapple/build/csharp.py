"""C# build backend — wraps dotnet/msbuild for iOS/macOS."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .orchestrator import BuildResult, run_cmd
from ..core.config import ProjectConfig, check_tool


class CSharpBackend:
    """Builds C# apps for iOS/macOS using .NET MAUI, Xamarin, or Mono."""

    def __init__(self, config: ProjectConfig):
        self.config = config

    def build(self, config: ProjectConfig, project_dir: Path,
              target: str = "ios", release: bool = False) -> BuildResult:
        """Build a C# project for the given target."""
        dotnet = check_tool("dotnet")
        if dotnet is None:
            return BuildResult(
                success=False,
                errors=["dotnet not found. Install from https://dotnet.microsoft.com/download"],
                language="csharp",
            )

        # Check for .NET MAUI, Xamarin, or Mono
        return self._build_with_dotnet(config, project_dir, target, release)

    def _build_with_dotnet(self, config: ProjectConfig, project_dir: Path,
                            target: str, release: bool) -> BuildResult:
        """Build using .NET CLI."""
        dotnet = check_tool("dotnet")

        # Detect project type
        csproj = list(project_dir.rglob("*.csproj"))
        if not csproj:
            return BuildResult(
                success=False,
                errors=["No .csproj file found. Run 'dotnet new' to create one."],
                language="csharp",
            )

        csproj_path = csproj[0]

        # Read project to determine type
        import xml.etree.ElementTree as ET
        tree = ET.parse(csproj_path)
        root = tree.getroot()

        # Check for MAUI
        ns = {"msbuild": "http://schemas.microsoft.com/developer/msbuild/2003"}
        is_maui = any(
            "maui" in (elem.text or "").lower()
            for elem in root.iter()
        )

        # Determine runtime identifier
        rid = self._get_runtime_identifier(target)

        # Build command
        cmd = [dotnet, "build", str(csproj_path)]
        if release:
            cmd.append("--configuration")
            cmd.append("Release")
        if rid:
            cmd.extend(["-r", rid])

        exit_code, stdout, stderr = run_cmd(cmd, cwd=project_dir, timeout=600)

        if exit_code != 0 and is_maui:
            # Try MAUI-specific build
            return self._build_maui(config, project_dir, target, release)

        # Find output artifact
        artifact = self._find_dotnet_artifact(project_dir, csproj_path, config.name, target)

        return BuildResult(
            success=exit_code == 0,
            output=stdout,
            artifact=artifact,
            errors=[stderr] if stderr and exit_code != 0 else [],
            language="csharp",
            metadata={"framework": "dotnet", "target": target},
        )

    def _build_maui(self, config: ProjectConfig, project_dir: Path,
                      target: str, release: bool) -> BuildResult:
        """Build using .NET MAUI."""
        dotnet = check_tool("dotnet")

        # MAUI has specific build commands
        target_map = {
            "ios": "ios",
            "ios-simulator": "ios",
            "macos": "macos",
        }
        maui_target = target_map.get(target, "ios")

        cmd = [dotnet, "maui", "build", "--target", maui_target]
        if release:
            cmd.append("--configuration=Release")

        exit_code, stdout, stderr = run_cmd(cmd, cwd=project_dir, timeout=1200)

        return BuildResult(
            success=exit_code == 0,
            output=stdout,
            errors=[stderr] if stderr and exit_code != 0 else [],
            language="csharp",
            metadata={"framework": "maui", "target": target},
        )

    def _get_runtime_identifier(self, target: str) -> str:
        """Map target to .NET Runtime Identifier."""
        mapping = {
            "ios": "ios-arm64",
            "ios-simulator": "iossimulator-x64",
            "macos": "osx-arm64",
        }
        return mapping.get(target, "")

    def _find_dotnet_artifact(self, project_dir: Path, csproj_path: Path,
                               name: str, target: str) -> Path | None:
        """Find the built .dll or executable."""
        patterns = {
            f"{name}.dll": 0,
            f"{name}.app": 1,
            f"{name}.ipa": 2,
        }
        candidates = []
        for p in project_dir.rglob("*"):
            if p.name in patterns:
                p_str = str(p)
                config_score = 0 if "Debug" in p_str else (1 if "Release" in p_str else 2)
                pattern_score = patterns[p.name]
                candidates.append((pattern_score, config_score, p))

        if not candidates:
            return None

        candidates.sort(key=lambda x: (x[0], x[1]))
        return candidates[0][2]


# Factory function for orchestrator
def create_csharp_backend(config: ProjectConfig) -> CSharpBackend:
    return CSharpBackend(config)