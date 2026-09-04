"""Kotlin build backend (Kotlin/Native for iOS/macOS, Kotlin Multiplatform for Android)."""

from __future__ import annotations

import os
from pathlib import Path

from ..core.config import ProjectConfig
from .orchestrator import BuildResult, run_cmd


class KotlinBackend:
    """Builds Kotlin projects for iOS, macOS, or Android.

    Routes:
      - target=android       -> ./gradlew assembleDebug (or assembleRelease)
      - target=ios           -> ./gradlew binaries --target iosArm64
      - target=ios-simulator -> ./gradlew binaries --target iosX64
      - target=macos         -> ./gradlew binaries --target macosArm64
    """

    def __init__(self, config: ProjectConfig):
        self.config = config

    def build(self, config: ProjectConfig, project_dir: Path,
              target: str = "ios", release: bool = False) -> BuildResult:
        """Build a Kotlin project for the given target."""
        # Check for Gradle wrapper
        gradlew = project_dir / "gradlew"
        if not gradlew.exists():
            return BuildResult(
                success=False,
                errors=["gradlew not found. Is this a Kotlin project?"],
                language="kotlin",
            )

        if target == "android":
            return self._build_android(config, project_dir, release)
        return self._build_native(config, project_dir, target, release)

    def _build_native(self, config: ProjectConfig, project_dir: Path,
                      target: str, release: bool) -> BuildResult:
        """Kotlin/Native build for iOS / macOS."""
        if target == "ios":
            kotlin_target = "iosArm64"
        elif target == "ios-simulator":
            kotlin_target = "iosX64"
        elif target == "macos":
            kotlin_target = "macosArm64"
        else:
            kotlin_target = "iosArm64"

        cmd = ["./gradlew", "binaries", "--target", kotlin_target]
        if release:
            cmd += ["-P", "kotlin.binary.release=true"]

        exit_code, stdout, stderr = run_cmd(cmd, cwd=project_dir, timeout=600)

        artifact = None
        build_dir = project_dir / "build" / "binaries"
        if build_dir.exists():
            for binary in build_dir.rglob(f"{config.name}*.kexe"):
                artifact = binary
                break
            if artifact is None:
                for binary in build_dir.rglob(f"{config.name}*.framework"):
                    artifact = binary
                    break

        return BuildResult(
            success=exit_code == 0,
            output=stdout,
            artifact=artifact,
            errors=[stderr] if stderr and exit_code != 0 else [],
            language="kotlin",
        )

    def _build_android(self, config: ProjectConfig, project_dir: Path,
                       release: bool) -> BuildResult:
        """Android build via Gradle (assembleDebug / assembleRelease)."""
        # Make sure gradlew is executable
        gradlew = project_dir / "gradlew"
        if not os.access(gradlew, os.X_OK):
            try:
                gradlew.chmod(0o755)
            except OSError:
                pass

        gradle_task = "assembleRelease" if release else "assembleDebug"
        cmd = ["./gradlew", gradle_task]

        # Forward JAVA_HOME (for gradle), ANDROID_HOME / ANDROID_SDK_ROOT (for SDK).
        # Without JAVA_HOME, gradlew may not find the right JDK on CI runners where
        # JAVA_HOME is set in the shell but not inherited by subprocesses.
        env = {}
        for env_var in ("JAVA_HOME", "ANDROID_HOME", "ANDROID_SDK_ROOT"):
            if os.environ.get(env_var):
                env[env_var] = os.environ[env_var]

        exit_code, stdout, stderr = run_cmd(
            cmd, cwd=project_dir, env=env, timeout=900,
        )

        # Locate APK: build/outputs/apk/<flavor>/.../*.apk
        artifact = None
        apk_dir = project_dir / "build" / "outputs" / "apk"
        if apk_dir.exists():
            candidates = sorted(
                apk_dir.rglob("*.apk"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            for apk in candidates:
                # Prefer release over debug if release was requested
                if release and "release" in apk.name:
                    artifact = apk
                    break
                if not release and "debug" in apk.name:
                    artifact = apk
                    break
            if artifact is None and candidates:
                artifact = candidates[0]

        # Detect common Android-build failure modes and report a useful hint
        errors: list[str] = []
        if exit_code != 0:
            hint = self._diagnose_android_failure(stderr or stdout)
            if hint:
                errors.append(hint)
            if stderr:
                errors.append(stderr.strip().splitlines()[-1] if stderr.strip() else "")
            elif stdout:
                errors.append(stdout.strip().splitlines()[-1] if stdout.strip() else "")
        elif artifact is None:
            errors.append(
                "Gradle build reported success but no APK was found in build/outputs/apk/."
            )

        return BuildResult(
            success=exit_code == 0 and artifact is not None,
            output=stdout,
            artifact=artifact,
            errors=errors,
            language="kotlin",
        )

    @staticmethod
    def _diagnose_android_failure(log: str) -> str:
        """Return a short, actionable hint for common Android build errors."""
        low = log.lower()
        if "android_sdk_root" in low or "sdk location not found" in low:
            return (
                "Android SDK not found. Set ANDROID_HOME or ANDROID_SDK_ROOT, "
                "or run: smart-apple-dev doctor --install"
            )
        if "jdk" in low and ("version" in low or "toolchain" in low or "tools.jar" in low):
            return "JDK 17+ required for Android Gradle Plugin. Install: apt install openjdk-17-jdk"
        if "java" in low and ("version" in low or "toolchain" in low or "tools.jar" in low):
            return "JDK 17+ required for Android Gradle Plugin. Install: apt install openjdk-17-jdk"
        if "licen" in low and "android" in low:
            return "Android SDK licenses not accepted. Run: yes | sdkmanager --licenses"
        if "permission" in low and "gradlew" in low:
            return "gradlew not executable. Run: chmod +x gradlew"
        return ""
