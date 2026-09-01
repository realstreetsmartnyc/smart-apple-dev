"""App Store Connect integration."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..build.orchestrator import run_cmd
from ..core.config import check_tool


@dataclass
class AscResult:
    """Result of an App Store Connect operation."""
    success: bool
    output: str = ""
    errors: list[str] = None
    app_id: str | None = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

    def to_dict(self) -> dict[str, Any]:
        return {"success": self.success, "output": self.output,
                "errors": self.errors, "app_id": self.app_id}


def check_asc_availability() -> dict[str, Any]:
    """Check if App Store Connect tools are available."""
    return {
        "fastlane": check_tool("fastlane") is not None,
        "altool": check_tool("altool") is not None,
        "asc_api": True,  # We can use the App Store Connect Swift SDK
    }


def upload_to_app_store(ipa_path: Path, config,
                        username: str | None = None,
                        password: str | None = None,
                        app_specific_password: str | None = None) -> AscResult:
    """Upload an .ipa to App Store Connect."""
    # Try fastlane first
    fastlane = check_tool("fastlane")
    if fastlane:
        return _upload_fastlane(ipa_path, config, username, password,
                                app_specific_password)

    # Try altool
    altool = check_tool("altool")
    if altool:
        return _upload_altool(ipa_path, config, username, password,
                              app_specific_password)

    return AscResult(
        success=False,
        errors=["No App Store Connect upload tool found. "
                "Install fastlane: brew install fastlane"],
    )


def _upload_fastlane(ipa_path: Path, config, username: str | None,
                    password: str | None,
                    app_specific_password: str | None) -> AscResult:
    """Upload using fastlane."""
    # Create a temporary Fastfile
    fastlane_dir = ipa_path.parent / "fastlane"
    fastlane_dir.mkdir(exist_ok=True)

    fastfile = fastlane_dir / "Fastfile"
    fastfile.write_text(f"""
lane :upload_to_app_store do
  pilot(
    ipa: \"{ipa_path}\",
    skip_waiting_for_build_processing: true,
    username: \"{username or 'YOUR_APPLE_ID'}\",
    app_specific_password: \"{app_specific_password or 'YOUR_APP_SPECIFIC_PASSWORD'}\"
  )
end
""")

    cmd = ["fastlane", "upload_to_app_store"]
    env = {}
    if username:
        env["FASTLANE_USER"] = username
    if password:
        env["FASTLANE_PASSWORD"] = password

    exit_code, stdout, stderr = run_cmd(cmd, cwd=fastlane_dir, env=env, timeout=600)

    return AscResult(
        success=exit_code == 0,
        output=stdout,
        errors=[stderr] if stderr and exit_code != 0 else [],
    )


def _upload_altool(ipa_path: Path, config, username: str | None,
                   password: str | None,
                   app_specific_password: str | None) -> AscResult:
    """Upload using altool."""
    cmd = ["altool", "--upload-app", "-f", str(ipa_path)]
    if username:
        cmd.extend(["-u", username])
    if app_specific_password:
        cmd.extend(["-p", app_specific_password])

    exit_code, stdout, stderr = run_cmd(cmd, timeout=600)

    return AscResult(
        success=exit_code == 0,
        output=stdout,
        errors=[stderr] if stderr and exit_code != 0 else [],
    )


def submit_for_review(app_id: str, username: str | None = None,
                      password: str | None = None,
                      skip_build_processing: bool = False,
                      platform: str = "ios") -> AscResult:
    """Submit an app for App Store review.

    Args:
        app_id: App Store Connect app ID.
        username: Apple ID email.
        password: Apple ID password.
        skip_build_processing: Skip waiting for build processing on App Store Connect.
        platform: Target platform (ios, macos, appletvos).
    """
    fastlane = check_tool("fastlane")
    if fastlane is None:
        return AscResult(
            success=False,
            errors=[
                "fastlane not found. Install with: brew install fastlane",
                "Or on Linux: download from https://download.fastlane.tools",
            ],
        )

    fastlane_dir = Path.home() / ".smart-apple-dev" / "fastlane"
    fastlane_dir.mkdir(parents=True, exist_ok=True)

    skip_str = "true" if skip_build_processing else "false"
    fastfile = fastlane_dir / "Fastfile"
    fastfile.write_text(f"""
lane :submit_for_review do
  deliver(
    app: "{app_id}",
    skip_waiting_for_build_processing: {skip_str},
    submit_for_review: true,
    platform: "{platform}",
    {f'username: "{username}",' if username else ''}
    {f'password: "{password}",' if password else ''}
  )
end
""")

    cmd = ["fastlane", "submit_for_review"]
    env = {}
    if username:
        env["FASTLANE_USER"] = username
    if password:
        env["FASTLANE_PASSWORD"] = password

    exit_code, stdout, stderr = run_cmd(cmd, cwd=fastlane_dir, env=env, timeout=600)

    return AscResult(
        success=exit_code == 0,
        output=stdout,
        errors=[stderr] if stderr and exit_code != 0 else [],
        app_id=app_id,
    )