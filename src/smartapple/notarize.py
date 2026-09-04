"""Notarization helper for macOS .app bundles.

On macOS: uses xcrun notarytool to upload to Apple's notary service and
xcrun stapler to attach the resulting ticket.

On Linux/Windows: only --remote (SSH) works. The user is expected to have
a Mac with `xcrun` available, configured with
`xcrun notarytool store-credentials <profile-name>`.

Credential setup (run once on the Mac):
    xcrun notarytool store-credentials <profile-name> \
        --apple-id <apple-id@example.com> \
        --team-id <TEAMID> \
        --password <app-specific-password>

The profile name becomes the --identity argument here.
"""

from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .core.config import check_tool, get_platform


@dataclass
class NotarizeResult:
    success: bool
    artifact_path: Path | None = None
    ticket_path: Path | None = None
    output: str = ""
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "artifact_path": str(self.artifact_path) if self.artifact_path else None,
            "ticket_path": str(self.ticket_path) if self.ticket_path else None,
            "output": self.output,
            "warnings": self.warnings,
            "errors": self.errors,
        }


def _make_zip_for_notary(app_path: Path, dest_zip: Path) -> bool:
    """Notarytool wants a zip (or dmg/pkg). For .app we zip the parent dir
    (so the zip contains YourApp.app/, not YourApp.app/Contents/...).

    Returns True on success.
    """
    if dest_zip.exists():
        dest_zip.unlink()
    parent = app_path.parent
    name = app_path.name
    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(app_path):
            for f in files:
                full = Path(root) / f
                # Path inside the zip: YourApp.app/<...>
                arcname = name + "/" + str(full.relative_to(app_path))
                z.write(full, arcname)
    return dest_zip.exists()


def _remote_notarize(artifact: Path, identity: str, remote_host: str,
                     bundle_id: str) -> NotarizeResult:
    """SSH into a Mac and run xcrun notarytool + stapler there."""
    ssh_target = f"{remote_host}"
    zip_local = artifact.parent / f"{artifact.name}-notarize.zip"
    if not _make_zip_for_notary(artifact, zip_local):
        return NotarizeResult(success=False, errors=[f"failed to zip {artifact}"])
    # scp the zip to the Mac
    remote_zip = f"/tmp/{zip_local.name}"
    r = subprocess.run(
        ["ssh", ssh_target, f"mkdir -p /tmp/notary-{bundle_id}"],
        capture_output=True, text=True, timeout=60,
    )
    if r.returncode != 0:
        return NotarizeResult(success=False, errors=[
            f"ssh mkdir failed: {r.stderr.strip()}"
        ])
    r = subprocess.run(
        ["scp", str(zip_local), f"{ssh_target}:{remote_zip}"],
        capture_output=True, text=True, timeout=600,
    )
    if r.returncode != 0:
        return NotarizeResult(success=False, errors=[
            f"scp failed: {r.stderr.strip()}"
        ])
    if not identity:
        return NotarizeResult(success=False, errors=[
            "--identity is required for notarization (the keychain profile name)"
        ])
    # Run notarytool on the Mac
    r = subprocess.run(
        ["ssh", ssh_target,
         f"cd /tmp && xcrun notarytool submit {remote_zip} "
         f"--keychain-profile {identity} --wait"],
        capture_output=True, text=True, timeout=1800,
    )
    if r.returncode != 0:
        return NotarizeResult(success=False, errors=[
            f"notarytool failed (exit {r.returncode}): {r.stderr.strip()}"
        ], output=r.stdout)
    # Staple
    r2 = subprocess.run(
        ["ssh", ssh_target,
         f"cd /tmp && unzip -o {remote_zip} > /dev/null && "
         f"xcrun stapler staple {artifact.name}"],
        capture_output=True, text=True, timeout=300,
    )
    return NotarizeResult(
        success=True,
        artifact_path=artifact,
        output=r.stdout,
        warnings=[] if r2.returncode == 0 else [f"stapler: {r2.stderr.strip()}"],
    )


def notarize_app(artifact_path: str, *, identity: str | None = None,
                 remote_host: str | None = None,
                 bundle_id: str = "") -> NotarizeResult:
    """Notarize a macOS .app bundle.

    Dispatches based on platform:
    - macOS + xcrun: run locally
    - Linux/Windows + --remote: SSH to a Mac
    - Otherwise: error with a clear message
    """
    p = Path(artifact_path)
    if not p.exists():
        return NotarizeResult(success=False, errors=[f"not found: {p}"])
    if p.suffix != ".app" and not (p.is_dir() and p.name.endswith(".app")):
        return NotarizeResult(
            success=False, errors=[f"expected a .app bundle, got {p}"])

    platform = get_platform()

    if platform == "macos" and check_tool("xcrun") is not None:
        if not identity:
            return NotarizeResult(success=False, errors=[
                "--identity is required (the keychain profile name). "
                "Set it up with: xcrun notarytool store-credentials <name>"
            ])
        zip_path = p.parent / f"{p.name}-notarize.zip"
        if not _make_zip_for_notary(p, zip_path):
            return NotarizeResult(success=False, errors=["zip creation failed"])
        r = subprocess.run(
            ["xcrun", "notarytool", "submit", str(zip_path),
             "--keychain-profile", identity, "--wait"],
            capture_output=True, text=True, timeout=1800,
        )
        if r.returncode != 0:
            return NotarizeResult(success=False, errors=[
                f"notarytool failed: {r.stderr.strip()}"
            ], output=r.stdout)
        # Staple
        r2 = subprocess.run(
            ["xcrun", "stapler", "staple", str(p)],
            capture_output=True, text=True, timeout=300,
        )
        zip_path.unlink(missing_ok=True)
        return NotarizeResult(
            success=True,
            artifact_path=p,
            output=r.stdout,
            warnings=[] if r2.returncode == 0 else [f"stapler: {r2.stderr.strip()}"],
        )

    if remote_host:
        return _remote_notarize(p, identity or "", remote_host, bundle_id)

    return NotarizeResult(success=False, errors=[
        f"Notarization from {platform} requires either:",
        f"  1. Run on macOS with xcrun available, and pass --identity <keychain-profile>",
        f"  2. Pass --remote user@mac-host to SSH to a Mac and notarize there",
    ])
