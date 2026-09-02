"""Game engine build backend — Unity, Godot, Unreal, SpriteKit, SceneKit, Metal."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from dataclasses import dataclass

from .orchestrator import BuildResult, run_cmd
from ..core.config import ProjectConfig, check_tool


@dataclass
class GameEngineConfig:
    """Configuration for game engine builds."""
    engine: str  # unity, godot, unreal, spritekit, scenekit, metal
    project_path: Path
    target: str  # ios, macos, tvos, android, web, desktop
    build_mode: str  # debug, release
    build_pipeline: str  # graphics, audio, physics, network, etc.


class GameEngineBackend:
    """Builds games using various engines: Unity, Godot, Unreal, SpriteKit, SceneKit, Metal."""

    def __init__(self, config: ProjectConfig):
        self.config = config
        self.extra = config.extra if hasattr(config, 'extra') else {}

    def build(self, config: ProjectConfig, project_dir: Path,
              target: str = "ios", release: bool = False) -> BuildResult:
        """Detect game engine and build accordingly."""
        engine = self._detect_engine(project_dir)
        if engine is None:
            return BuildResult(
                success=False,
                errors=["No recognized game engine found. Expected Unity, Godot, "
                        "Unreal, SpriteKit, SceneKit, or Metal project files."],
                language="game",
            )

        build_mode = "release" if release else "debug"
        return self._build_with_engine(engine, config, project_dir, target, build_mode)

    def _detect_engine(self, project_dir: Path) -> str | None:
        """Auto-detect the game engine from project files."""
        if (project_dir / "ProjectSettings" / "ProjectVersion.txt").exists():
            return "unity"
        if (project_dir / "project.godot").exists():
            return "godot"
        if (project_dir / "Config" / "DefaultEngine.ini").exists():
            return "unreal"
        if (project_dir / "Sources" / "Scenes").exists():
            return "spritekit"
        if list(project_dir.rglob("*.metal")):
            return "metal"
        if list(project_dir.rglob("*.scn")) or list(project_dir.rglob("*.dae")):
            return "scenekit"
        if self.extra.get("engine") in ("unity", "godot", "unreal", "spritekit", "scenekit", "metal"):
            return self.extra.get("engine")
        return None

    def _build_with_engine(self, engine: str, config: ProjectConfig,
                            project_dir: Path, target: str, build_mode: str) -> BuildResult:
        """Build using the detected engine."""
        builders = {
            "unity": self._build_unity,
            "godot": self._build_godot,
            "unreal": self._build_unreal,
            "spritekit": self._build_spritekit,
            "scenekit": self._build_scenekit,
            "metal": self._build_metal,
        }
        builder = builders.get(engine)
        if builder is None:
            return BuildResult(
                success=False,
                errors=[f"Unknown game engine: {engine}"],
                language="game",
            )
        return builder(config, project_dir, target, build_mode)

    # ---- Unity ----
    def _build_unity(self, config: ProjectConfig, project_dir: Path,
                      target: str, build_mode: str) -> BuildResult:
        """Build Unity project via Unity CLI or batchmode."""
        unity = check_tool("unity-editor")
        if unity is None:
            # Try Unity Hub
            unity = check_tool("unityhub")
        if unity is None:
            # Fall back to external tool
            unity_cmd = os.environ.get("UNITY_PATH")
            if unity_cmd:
                unity = unity_cmd
            else:
                return BuildResult(
                    success=False,
                    errors=["Unity not found. Install Unity Hub from unity.com/download"],
                    language="game",
                )

        # Unity batch mode build
        build_target = self._unity_target(target)
        output_ext = self._unity_output_ext(target)
        output_dir = project_dir / "build" / target
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{config.name}{output_ext}"

        scenes = self._get_unity_scenes(project_dir)
        scene_arg = " ".join(f'"{s}"' for s in scenes) if scenes else ""

        cmd = [
            unity, "-batchmode", "-quit",
            "-projectPath", str(project_dir),
            "-buildTarget", build_target,
            "-executeMethod", f"UnityEditor.BuildPlayerWindow.BuildPlayer({scene_arg})",
            "-buildOutput", str(output_path),
            "-logFile", str(project_dir / "unity_build.log"),
        ]
        if build_mode == "release":
            cmd.append("-buildType release")

        exit_code, stdout, stderr = run_cmd(cmd, cwd=project_dir, timeout=1800)

        # Read log for errors
        log_file = project_dir / "unity_build.log"
        if log_file.exists():
            with open(log_file) as f:
                log_content = f.read()
            if "Error" in log_content:
                stderr = log_content

        return BuildResult(
            success=exit_code == 0,
            output=stdout,
            artifact=output_path if output_path.exists() else None,
            errors=[stderr] if stderr and exit_code != 0 else [],
            language="game",
            metadata={"engine": "unity", "target": target, "build_mode": build_mode},
        )

    def _unity_target(self, target: str) -> str:
        mapping = {
            "ios": "iOS",
            "ios-simulator": "iOS",
            "macos": "MacStandalone",
            "tvos": "tvOS",
            "android": "Android",
            "web": "WebGL",
        }
        return mapping.get(target, "iOS")

    def _unity_output_ext(self, target: str) -> str:
        mapping = {
            "ios": ".ipa",
            "ios-simulator": ".app",
            "macos": ".app",
            "tvos": ".ipa",
            "android": ".apk",
            "web": "",
        }
        return mapping.get(target, ".app")

    def _get_unity_scenes(self, project_dir: Path) -> list[str]:
        scenes = []
        scenes_dir = project_dir / "Assets" / "Scenes"
        if scenes_dir.exists():
            for scene in scenes_dir.rglob("*.unity"):
                rel = scene.relative_to(project_dir)
                scenes.append(str(rel))
        if not scenes:
            default_scene = project_dir / "Assets" / "Scenes" / "SampleScene.unity"
            if default_scene.exists():
                scenes.append("Assets/Scenes/SampleScene.unity")
        return scenes

    # ---- Godot ----
    def _build_godot(self, config: ProjectConfig, project_dir: Path,
                      target: str, build_mode: str) -> BuildResult:
        """Build Godot project."""
        godot = check_tool("godot")
        if godot is None:
            return BuildResult(
                success=False,
                errors=["Godot not found. Install from godotengine.org"],
                language="game",
            )

        godot_target = self._godot_export_preset(target)
        if godot_target is None:
            return BuildResult(
                success=False,
                errors=[f"No export preset for target: {target}"],
                language="game",
            )

        output_dir = project_dir / "build" / target
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{config.name}"

        # Godot headless export
        cmd = [
            godot, "--headless",
            "--path", str(project_dir),
            "--export-release" if build_mode == "release" else "--export-debug",
            godot_target,
            str(output_file),
        ]

        exit_code, stdout, stderr = run_cmd(cmd, cwd=project_dir, timeout=1800)

        return BuildResult(
            success=exit_code == 0,
            output=stdout,
            artifact=output_file if output_file.exists() else None,
            errors=[stderr] if stderr and exit_code != 0 else [],
            language="game",
            metadata={"engine": "godot", "target": target, "build_mode": build_mode},
        )

    def _godot_export_preset(self, target: str) -> str | None:
        mapping = {
            "ios": "iOS",
            "ios-simulator": "iOS",
            "macos": "Mac OSX",
            "tvos": "tvOS",
            "android": "Android",
            "web": "HTML5",
        }
        return mapping.get(target)

    # ---- Unreal ----
    def _build_unreal(self, config: ProjectConfig, project_dir: Path,
                       target: str, build_mode: str) -> BuildResult:
        """Build Unreal Engine project."""
        # Unreal uses BuildCookRun or UAT
        uat = check_tool("BuildCookRun")
        if uat is None:
            uat = os.environ.get("UNREAL_ENGINE_ROOT")
            if uat:
                uat = Path(uat) / "Engine" / "Build" / "BatchFiles" / "Mac" / "BuildCookRun.sh"
            else:
                return BuildResult(
                    success=False,
                    errors=["Unreal Engine not found. Set UNREAL_ENGINE_ROOT or install UE."],
                    language="game",
                )

        platform = self._unreal_platform(target)
        config_type = "Shipping" if build_mode == "release" else "Development"

        cmd = [
            str(uat),
            "-project=" + str(project_dir / f"{config.name}.uproject"),
            "-platform", platform,
            "-build", "-cook", "-stage",
            "-package",
            "-clientconfig=" + config_type,
        ]

        exit_code, stdout, stderr = run_cmd(cmd, cwd=project_dir, timeout=3600)

        return BuildResult(
            success=exit_code == 0,
            output=stdout,
            errors=[stderr] if stderr and exit_code != 0 else [],
            language="game",
            metadata={"engine": "unreal", "target": target, "build_mode": build_mode},
        )

    def _unreal_platform(self, target: str) -> str:
        mapping = {
            "ios": "IOS",
            "ios-simulator": "IOS",
            "macos": "Mac",
            "tvos": "TVOS",
        }
        return mapping.get(target, "IOS")

    # ---- SpriteKit ----
    def _build_spritekit(self, config: ProjectConfig, project_dir: Path,
                          target: str, build_mode: str) -> BuildResult:
        """Build SpriteKit game using xtool."""
        xtool = check_tool("xtool")
        if xtool is None:
            return BuildResult(
                success=False,
                errors=["xtool not found. Install: curl -fsSL https://xtool.sh/install.sh | bash"],
                language="game",
            )

        target_triple = self._spritekit_target(target)
        cmd = [xtool, "build", "--target", target_triple]
        if build_mode == "release":
            cmd.extend(["-c", "release"])

        exit_code, stdout, stderr = run_cmd(cmd, cwd=project_dir, timeout=600)

        return BuildResult(
            success=exit_code == 0,
            output=stdout,
            errors=[stderr] if stderr and exit_code != 0 else [],
            language="game",
            metadata={"engine": "spritekit", "target": target, "build_mode": build_mode},
        )

    def _spritekit_target(self, target: str) -> str:
        mapping = {
            "ios": "ios",
            "ios-simulator": "ios-simulator",
            "macos": "macos",
            "tvos": "tvos",
        }
        return mapping.get(target, "ios")

    # ---- SceneKit ----
    def _build_scenekit(self, config: ProjectConfig, project_dir: Path,
                         target: str, build_mode: str) -> BuildResult:
        """Build SceneKit 3D game."""
        return self._build_spritekit(config, project_dir, target, build_mode)

    # ---- Metal ----
    def _build_metal(self, config: ProjectConfig, project_dir: Path,
                      target: str, build_mode: str) -> BuildResult:
        """Build Metal app with custom shaders."""
        xtool = check_tool("xtool")
        if xtool is None:
            clang = check_tool("clang")
            if clang is None:
                return BuildResult(
                    success=False,
                    errors=["Neither xtool nor clang found for Metal build"],
                    language="game",
                )

        target_triple = self._metal_target(target)
        cmd = [xtool, "build", "--target", target_triple]
        if build_mode == "release":
            cmd.extend(["-c", "release"])

        exit_code, stdout, stderr = run_cmd(cmd, cwd=project_dir, timeout=600)

        return BuildResult(
            success=exit_code == 0,
            output=stdout,
            errors=[stderr] if stderr and exit_code != 0 else [],
            language="game",
            metadata={"engine": "metal", "target": target, "build_mode": build_mode},
        )

    def _metal_target(self, target: str) -> str:
        mapping = {
            "ios": "ios",
            "ios-simulator": "ios-simulator",
            "macos": "macos",
            "tvos": "tvos",
        }
        return mapping.get(target, "ios")
