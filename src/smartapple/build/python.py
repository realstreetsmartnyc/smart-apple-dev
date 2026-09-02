"""Python build backend — Python-to-iOS transpiler or native wrapper."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .orchestrator import BuildResult, run_cmd
from ..core.config import ProjectConfig, check_tool


class PythonBackend:
    """Builds Python apps for iOS/macOS using transpilers or native bridges."""

    def __init__(self, config: ProjectConfig):
        self.config = config

    def build(self, config: ProjectConfig, project_dir: Path,
              target: str = "ios", release: bool = False) -> BuildResult:
        """Build a Python project for the target platform."""
        # Check for available Python build tools
        python = check_tool("python3")
        if python is None:
            python = check_tool("python")

        if python is None:
            return BuildResult(
                success=False,
                errors=["Python not found. Install from https://python.org/"],
                language="python",
            )

        # Check for platform-specific build tools
        if target in ("ios", "ios-simulator", "macos"):
            return self._build_for_apple_platform(config, project_dir, target, release)

        return self._build_generic(config, project_dir, target, release)

    def _build_for_apple_platform(self, config: ProjectConfig, project_dir: Path,
                                   target: str, release: bool) -> BuildResult:
        """Build Python for Apple platforms."""
        # Check for Kivy
        kivy_deps = ["Kivy", "Buildozer"]
        kivy_available = all(
            any((Path(p) / dep).exists() for p in (check_tool("python3"),) if check_tool("python3")) for dep in kivy_deps
        )

        if kivy_available:
            return self._build_with_kivy(config, project_dir, target, release)

        # Check for BeeWare
        bee_ware = check_tool("briefcase")
        if bee_ware is not None:
            return self._build_with_beeware(config, project_dir, target, release)

        # Check for Pyto (Python-iOS interpreter)
        pyto = check_tool("pyto")
        if pyto is not None:
            return self._build_with_pyto(config, project_dir, target, release)

        # Check for Pythonista
        pythonista = check_tool("pythonista")
        if pythonista is not None:
            return self._build_with_pythonista(config, project_dir, target, release)

        # Last resort: Use PyObjC
        pyobjc = check_tool("pyobjc")
        if pyobjc is not None:
            return self._build_with_pyobjc(config, project_dir, target, release)

        return BuildResult(
            success=False,
            errors=["No compatible Python build system found for iOS/macOS. "
                    "Install Kivy, BeeWare, Pyto, or ensure PyObjC is available."],
            language="python",
        )

    def _build_with_kivy(self, config: ProjectConfig, project_dir: Path,
                          target: str, release: bool) -> BuildResult:
        """Build using Kivy framework."""
        # Check for Buildozer
        buildozer = check_tool("buildozer")
        if buildozer is None:
            return BuildResult(
                success=False,
                errors=["buildozer not found. Install with: pip install buildozer"],
                language="python",
            )

        cmd = [buildozer, "android", "--clean"]
        if release:
            cmd.append("--release")

        exit_code, stdout, stderr = run_cmd(cmd, cwd=project_dir, timeout=600)

        return BuildResult(
            success=exit_code == 0,
            output=stdout,
            errors=[stderr] if stderr and exit_code != 0 else [],
            language="python",
            metadata={"framework": "kivy"},
        )

    def _build_with_beeware(self, config: ProjectConfig, project_dir: Path,
                             target: str, release: bool) -> BuildResult:
        """Build using BeeWare tools."""
        # Briefcase is the tool
        briefcase = check_tool("briefcase")
        if briefcase is None:
            return BuildResult(
                success=False,
                errors=["briefcase not found. Install with: pip install briefcase"],
                language="python",
            )

        cmd = [briefcase, "create", config.name, "--platform", target]
        if release:
            cmd.append("--release")

        exit_code, stdout, stderr = run_cmd(cmd, cwd=project_dir, timeout=600)

        # Find the generated app
        app_dir = project_dir / f"build/{target}/{config.name}"
        if app_dir.exists():
            return BuildResult(
                success=True,
                output=stdout,
                artifact=app_dir,
                errors=[],
                language="python",
                metadata={"framework": "beeware"},
            )

        return BuildResult(
            success=False,
            output=stdout,
            errors=[f"BeeWare build failed: {stderr}"],
            language="python",
        )

    def _build_with_pyto(self, config: ProjectConfig, project_dir: Path,
                          target: str, release: bool) -> BuildResult:
        """Build using Pyto (Python-iOS interpreter)."""
        # Pyto uses its own build system
        cmd = ["pyto", "build", config.name, "--target", target]
        if release:
            cmd.append("--release")

        exit_code, stdout, stderr = run_cmd(cmd, cwd=project_dir, timeout=600)

        return BuildResult(
            success=exit_code == 0,
            output=stdout,
            errors=[stderr] if stderr and exit_code != 0 else [],
            language="python",
            metadata={"framework": "pyto"},
        )

    def _build_with_pythonista(self, config: ProjectConfig, project_dir: Path,
                               target: str, release: bool) -> BuildResult:
        """Build using Pythonista (Pythonista app)."""
        return BuildResult(
            success=False,
            errors=["Pythonista build not supported via CLI. Use Pythonista IDE."],
            language="python",
            metadata={"framework": "pythonista"},
        )

    def _build_with_pyobjc(self, config: ProjectConfig, project_dir: Path,
                            target: str, release: bool) -> BuildResult:
        """Build Python using PyObjC."""
        # Compile Python with PyObjC bridge
        import glob

        py_files = glob.glob(str(project_dir / "*.py"))
        if not py_files:
            py_files = list(project_dir.rglob("*.py"))

        if not py_files:
            return BuildResult(
                success=False,
                errors=["No .py files found in project"],
                language="python",
            )

        # Find build directory
        build_dir = project_dir / "build" / target
        build_dir.mkdir(parents=True, exist_ok=True)

        # Simple Python compilation to .so
        for py_file in py_files:
            py_name = py_file.stem
            pyc_path = build_dir / f"{py_name}.so"

            cmd = [
                check_tool("python3"), "-c",
                f"from py_compile import compile; compile(r'{py_file}', r'{pyc_path}.pyc', r'{pyc_path}.pyc')"
            ]
            exit_code, stdout, stderr = run_cmd(cmd, cwd=project_dir)

            if exit_code != 0:
                return BuildResult(
                    success=False,
                    output=stdout,
                    errors=[f"Python compilation failed for {py_file.name}: {stderr}"],
                    language="python",
                )

        return BuildResult(
            success=True,
            output=f"Python files compiled to {build_dir}",
            artifact=build_dir,
            errors=[],
            language="python",
            metadata={"framework": "pyobjc"},
        )

    def _build_generic(self, config: ProjectConfig, project_dir: Path,
                        target: str, release: bool) -> BuildResult:
        """Build generic Python for any platform."""
        # Use pyproject.toml or setup.py
        if (project_dir / "pyproject.toml").exists():
            return self._build_with_pyproject(config, project_dir, target, release)
        elif (project_dir / "setup.py").exists():
            return self._build_with_setup(config, project_dir, target, release)
        else:
            return self._build_simple_py(config, project_dir, target, release)

    def _build_with_pyproject(self, config: ProjectConfig, project_dir: Path,
                               target: str, release: bool) -> BuildResult:
        """Build using pyproject.toml (PEP 517)."""
        python = check_tool("python3") or check_tool("python")
        if python is None:
            return BuildResult(
                success=False,
                errors=["Python not found"],
                language="python",
            )

        # Install project in development mode
        cmd = [python, "-m", "pip", "install", "-e", "."]
        exit_code, stdout, stderr = run_cmd(cmd, cwd=project_dir, timeout=300)

        if exit_code != 0:
            return BuildResult(
                success=False,
                output=stdout,
                errors=[f"Failed to install package: {stderr}"],
                language="python",
            )

        # Build wheel
        wheel_cmd = [python, "-m", "build"]
        if release:
            wheel_cmd.extend(["--release"])

        exit_code, stdout, stderr = run_cmd(wheel_cmd, cwd=project_dir, timeout=600)

        # Find wheel
        dist_dir = project_dir / "dist"
        if dist_dir.exists():
            wheels = list(dist_dir.glob("*.whl"))
            if wheels:
                return BuildResult(
                    success=exit_code == 0,
                    output=stdout,
                    artifact=wheels[0],
                    errors=[stderr] if stderr and exit_code != 0 else [],
                    language="python",
                    metadata={"framework": "pip"},
                )

        return BuildResult(
            success=False,
            output=stdout,
            errors=[f"Build failed: {stderr}"],
            language="python",
        )

    def _build_with_setup(self, config: ProjectConfig, project_dir: Path,
                           target: str, release: bool) -> BuildResult:
        """Build using setup.py."""
        python = check_tool("python3") or check_tool("python")
        if python is None:
            return BuildResult(
                success=False,
                errors=["Python not found"],
                language="python",
            )

        cmd = [python, "setup.py", "build"]
        if release:
            cmd.append("--release")

        exit_code, stdout, stderr = run_cmd(cmd, cwd=project_dir, timeout=600)

        return BuildResult(
            success=exit_code == 0,
            output=stdout,
            errors=[stderr] if stderr and exit_code != 0 else [],
            language="python",
            metadata={"framework": "setup.py"},
        )

    def _build_simple_py(self, config: ProjectConfig, project_dir: Path,
                         target: str, release: bool) -> BuildResult:
        """Simple Python build (no packaging)."""
        # Just compile Python files
        import glob

        py_files = glob.glob(str(project_dir / "*.py"))
        if not py_files:
            py_files = list(project_dir.rglob("*.py"))

        if not py_files:
            return BuildResult(
                success=False,
                errors=["No Python files found"],
                language="python",
            )

        build_dir = project_dir / "build" / target
        build_dir.mkdir(parents=True, exist_ok=True)

        python = check_tool("python3") or check_tool("python")
        if python is None:
            return BuildResult(
                success=False,
                errors=["Python not found"],
                language="python",
            )

        for py_file in py_files:
            py_name = py_file.stem
            pyc_path = build_dir / f"{py_name}.pyc"

            cmd = [python, "-m", "compileall", "-o", str(build_dir), str(py_file)]
            exit_code, stdout, stderr = run_cmd(cmd, cwd=project_dir)

            if exit_code != 0:
                return BuildResult(
                    success=False,
                    output=stdout,
                    errors=[f"Python compilation failed for {py_file.name}: {stderr}"],
                    language="python",
                )

        return BuildResult(
            success=True,
            output=f"Python files compiled to {build_dir}",
            artifact=build_dir,
            errors=[],
            language="python",
            metadata={"framework": "builtin"},
        )


# Factory function for orchestrator
def create_python_backend(config: ProjectConfig) -> PythonBackend:
    return PythonBackend(config)