"""App signing and IPA packaging for smart-apple-dev.

On Linux/Windows, real Apple code signing requires tools that don't have
prebuilt binaries (ldid, cctools-port's codesign). This module:

1. Detects available signing tools (ldid, codesign, cctools)
2. Falls back to ad-hoc signing where possible
3. Always supports IPA packaging (the zip with Payload/ root)
4. Embeds provisioning profiles
5. Provides a `sign` command that works in three modes:
   - ad-hoc (default, no certs)
   - identity (real Apple developer cert via ldid)
   - skip (no signing, useful for testing)
"""

from __future__ import annotations

import os
import plistlib
import shutil
import struct
import subprocess
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..build.orchestrator import run_cmd
from ..core.config import ProjectConfig, check_tool, get_tool_dir


# ============================================================
# Tool detection
# ============================================================

def find_ldid() -> str | None:
    """Find ldid binary anywhere on disk."""
    p = check_tool("ldid")
    if p:
        return p
    # Also check the user tool dir explicitly
    tool_dir = get_tool_dir()
    candidate = tool_dir / "ldid"
    if candidate.exists() and os.access(candidate, os.X_OK):
        return str(candidate)
    return None


def find_codesign() -> str | None:
    """Find Apple's codesign (or cctools-port's codesign)."""
    for name in ("codesign", "darwin-codesign", "apple-codesign"):
        p = check_tool(name)
        if p:
            return p
    return None


def find_signing_tool() -> tuple[str | None, str]:
    """Find the best available signing tool. Returns (path, kind)."""
    ldid = find_ldid()
    if ldid:
        return ldid, "ldid"
    cs = find_codesign()
    if cs:
        return cs, "codesign"
    return None, "none"


# ============================================================
# Result types
# ============================================================

@dataclass
class SignResult:
    """Result of a signing operation."""
    success: bool
    artifact_path: Path | None = None
    signed: bool = False
    errors: list[str] = field(default_factory=list)
    output: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "artifact_path": str(self.artifact_path) if self.artifact_path else None,
            "signed": self.signed,
            "errors": self.errors,
            "warnings": self.warnings,
            "output": self.output,
        }


# ============================================================
# Signer
# ============================================================

class Signer:
    """Signs iOS/macOS apps.

    Modes:
    - "ad-hoc" (default): ldid -S without cert, or codesign --sign -
    - "identity": ldid -s <identity> or codesign --sign <identity>
    - "skip": no signing (for testing the build pipeline)
    """

    def __init__(self, config: ProjectConfig | None = None):
        self.config = config

    def sign(self, artifact: Path, config: ProjectConfig,
             mode: str = "ad-hoc",
             identity: str | None = None,
             provisioning_profile: Path | None = None,
             entitlements: Path | None = None) -> SignResult:
        """Sign a .app or .ipa.

        Args:
            artifact: path to .app or .ipa
            config: project config
            mode: "ad-hoc", "identity", or "skip"
            identity: Apple developer identity name (for mode="identity")
            provisioning_profile: path to .mobileprovision (for iOS)
            entitlements: path to entitlements.plist
        """
        if not artifact.exists():
            return SignResult(success=False, errors=[f"Artifact not found: {artifact}"])

        if artifact.suffix == ".ipa":
            return self._sign_ipa(artifact, config, mode, identity,
                                  provisioning_profile, entitlements)
        elif artifact.suffix == ".app" or artifact.is_dir():
            return self._sign_app(artifact, config, mode, identity,
                                  provisioning_profile, entitlements)
        else:
            return SignResult(success=False, errors=[f"Unknown artifact type: {artifact}"])

    def _sign_app(self, app_path: Path, config: ProjectConfig,
                  mode: str, identity: str | None,
                  provisioning_profile: Path | None,
                  entitlements: Path | None) -> SignResult:
        """Sign a .app bundle."""
        warnings: list[str] = []

        # For iOS: embed provisioning profile first (before signing)
        if provisioning_profile and provisioning_profile.exists():
            # iOS uses embedded.mobileprovision at the root of the .app
            embed_path = app_path / "embedded.mobileprovision"
            shutil.copy2(provisioning_profile, embed_path)
        elif _is_ios_app(app_path):
            warnings.append(
                "No provisioning profile embedded. iOS device install will fail "
                "without a valid profile."
            )

        # For iOS: also need _CodeSignature/ directory
        # ldid creates this automatically
        # codesign creates it automatically

        if mode == "skip":
            return SignResult(
                success=True,
                artifact_path=app_path,
                signed=False,
                warnings=warnings + ["Signing skipped (mode=skip)"],
            )

        if mode == "ad-hoc":
            return self._sign_adhoc(app_path, config, entitlements, warnings)
        if mode == "identity":
            if not identity:
                return SignResult(
                    success=False,
                    errors=["mode=identity requires an --identity argument"],
                )
            return self._sign_with_identity(app_path, identity, entitlements, warnings)

        return SignResult(success=False, errors=[f"Unknown signing mode: {mode}"])

    def _sign_adhoc(self, app_path: Path, config: ProjectConfig,
                    entitlements: Path | None,
                    warnings: list[str]) -> SignResult:
        """Ad-hoc sign without a real certificate."""
        # Find the main executable
        binary = self._find_executable(app_path, config)
        if binary is None:
            return SignResult(
                success=False,
                errors=[f"Could not find executable inside {app_path}"],
            )

        tool, kind = find_signing_tool()
        if kind == "ldid":
            return self._sign_with_ldid(tool, binary, app_path, entitlements, identity=None)
        if kind == "codesign":
            return self._sign_with_codesign(tool, binary, app_path, entitlements, identity="-")
        # No signing tool available
        return SignResult(
            success=True,  # The .app is still valid; just not signed
            artifact_path=app_path,
            signed=False,
            warnings=warnings + [
                "No signing tool found (ldid, codesign). Build is unsigned.",
                "To install on a real iOS device, build ldid from source:",
                "  git clone https://github.com/saurik/ldid.git && cd ldid",
                "  g++ -I . -o ldid ldid.cpp util.cpp -lcrypto -lpthread",
                f"  cp ldid {get_tool_dir()}/ldid",
            ],
        )

    def _sign_with_identity(self, app_path: Path, identity: str,
                            entitlements: Path | None,
                            warnings: list[str]) -> SignResult:
        """Sign with a specific Apple developer identity."""
        binary = self._find_executable(app_path, self.config)
        if binary is None:
            return SignResult(
                success=False,
                errors=[f"Could not find executable inside {app_path}"],
            )

        tool, kind = find_signing_tool()
        if kind == "ldid":
            return self._sign_with_ldid(tool, binary, app_path, entitlements, identity=identity)
        if kind == "codesign":
            return self._sign_with_codesign(tool, binary, app_path, entitlements, identity=identity)

        return SignResult(
            success=False,
            errors=[
                "No signing tool found. Cannot sign with identity.",
                "Install ldid: see smart-apple-dev doctor",
            ],
        )

    def _sign_with_ldid(self, ldid: str, binary: Path, app_path: Path,
                        entitlements: Path | None,
                        identity: str | None) -> SignResult:
        """Sign using ldid."""
        cmd = [ldid]
        if entitlements and entitlements.exists():
            cmd.append(f"-S{entitlements}")
        else:
            cmd.append("-S")  # ad-hoc with no entitlements
        if identity:
            cmd.extend(["-s", identity])
        cmd.append(str(binary))

        exit_code, stdout, stderr = run_cmd(cmd, timeout=60)
        if exit_code != 0:
            return SignResult(
                success=False,
                errors=[f"ldid failed: {stderr or stdout}"],
                output=stdout,
            )

        return SignResult(
            success=True,
            artifact_path=app_path,
            signed=True,
            output=stdout,
        )

    def _sign_with_codesign(self, codesign: str, binary: Path, app_path: Path,
                            entitlements: Path | None,
                            identity: str | None) -> SignResult:
        """Sign using Apple codesign (or cctools-port equivalent)."""
        cmd = [codesign, "--sign", identity or "-", "--force",
               "--timestamp=none",  # don't contact network for timestamps
               ]
        if entitlements and entitlements.exists():
            cmd.extend(["--entitlements", str(entitlements)])
        cmd.append(str(app_path))

        exit_code, stdout, stderr = run_cmd(cmd, timeout=60)
        if exit_code != 0:
            return SignResult(
                success=False,
                errors=[f"codesign failed: {stderr or stdout}"],
                output=stdout,
            )

        return SignResult(
            success=True,
            artifact_path=app_path,
            signed=True,
            output=stdout,
        )

    def _sign_ipa(self, ipa_path: Path, config: ProjectConfig,
                  mode: str, identity: str | None,
                  provisioning_profile: Path | None,
                  entitlements: Path | None) -> SignResult:
        """Sign an existing .ipa file (extract, sign, repack)."""
        # Extract
        extract_dir = ipa_path.parent / f".{ipa_path.stem}_extract"
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        extract_dir.mkdir(parents=True)

        try:
            with zipfile.ZipFile(ipa_path, "r") as zf:
                zf.extractall(extract_dir)

            # Find .app
            app_path = None
            payload = extract_dir / "Payload"
            if payload.exists():
                for item in payload.iterdir():
                    if item.is_dir() and item.name.endswith(".app"):
                        app_path = item
                        break

            if app_path is None:
                return SignResult(
                    success=False,
                    errors=["No .app found in IPA"],
                )

            # Sign the .app
            result = self._sign_app(app_path, config, mode, identity,
                                    provisioning_profile, entitlements)
            if not result.success:
                return result

            # Re-pack as new IPA
            new_ipa = ipa_path.parent / f"{config.name}-signed.ipa"
            if new_ipa.exists():
                new_ipa.unlink()
            with zipfile.ZipFile(new_ipa, "w", zipfile.ZIP_DEFLATED) as zf:
                for item in extract_dir.rglob("*"):
                    if item.is_file():
                        arcname = item.relative_to(extract_dir)
                        zf.write(item, arcname)

            return SignResult(
                success=True,
                artifact_path=new_ipa,
                signed=result.signed,
                output=result.output,
                warnings=result.warnings,
            )
        finally:
            # Cleanup extract dir
            if extract_dir.exists():
                shutil.rmtree(extract_dir)

    def _find_executable(self, app_path: Path, config: ProjectConfig) -> Path | None:
        """Find the main executable inside a .app bundle."""
        # macOS: <App>.app/Contents/MacOS/<exec>
        macos_dir = app_path / "Contents" / "MacOS"
        if macos_dir.exists():
            for child in macos_dir.iterdir():
                if child.is_file() and not child.suffix:
                    return child
            # Fallback: try by config name
            candidate = macos_dir / config.name
            if candidate.exists():
                return candidate

        # iOS: <App>.app/<exec>
        for child in app_path.iterdir():
            if child.is_file() and not child.suffix and os.access(child, os.X_OK):
                return child

        return None


# ============================================================
# IPA packaging
# ============================================================

def package_ipa(app_path: Path, output: Path | None = None) -> Path:
    """Package a .app bundle into an .ipa file.

    IPA format: a zip archive with:
      Payload/<AppName>.app/...

    Optionally contains an iTunesArtwork file (not required for install).
    """
    if not app_path.exists():
        raise FileNotFoundError(f"App bundle not found: {app_path}")
    if not app_path.name.endswith(".app"):
        raise ValueError(f"Not a .app bundle: {app_path}")

    if output is None:
        output = app_path.parent / f"{app_path.stem}.ipa"

    # Create the zip with Payload/ root
    if output.exists():
        output.unlink()

    payload_dir = app_path.parent / "Payload"
    if payload_dir.exists():
        shutil.rmtree(payload_dir)
    payload_dir.mkdir()

    # Copy .app into Payload/
    app_in_payload = payload_dir / app_path.name
    shutil.copytree(app_path, app_in_payload)

    try:
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
            for item in payload_dir.rglob("*"):
                if item.is_file():
                    arcname = item.relative_to(app_path.parent)  # yields "Payload/..."
                    zf.write(item, arcname)
    finally:
        shutil.rmtree(payload_dir)

    return output


def verify_ipa(ipa_path: Path) -> dict[str, Any]:
    """Verify an IPA file structure."""
    result: dict[str, Any] = {
        "valid": False,
        "path": str(ipa_path),
        "has_payload": False,
        "has_app": False,
        "app_name": None,
        "file_count": 0,
        "size_bytes": 0,
        "errors": [],
    }

    if not ipa_path.exists():
        result["errors"].append("IPA file does not exist")
        return result

    result["size_bytes"] = ipa_path.stat().st_size

    try:
        with zipfile.ZipFile(ipa_path, "r") as zf:
            names = zf.namelist()
            result["file_count"] = len(names)

            # Check for Payload/
            payload_entries = [n for n in names if n.startswith("Payload/")]
            if payload_entries:
                result["has_payload"] = True
                # Find the .app
                app_entries = [n for n in payload_entries if ".app/" in n]
                if app_entries:
                    result["has_app"] = True
                    # Extract app name
                    first = app_entries[0]
                    parts = first.split("/")
                    if len(parts) >= 2:
                        result["app_name"] = parts[1]
            else:
                result["errors"].append("No Payload/ directory in IPA")
    except zipfile.BadZipFile as e:
        result["errors"].append(f"Not a valid zip: {e}")
        return result

    result["valid"] = result["has_payload"] and result["has_app"]
    return result


# ============================================================
# Provisioning profiles
# ============================================================

def create_provisioning_profile(name: str, bundle_id: str,
                                device_ids: list[str] | None = None,
                                team_id: str = "YOUR_TEAM_ID") -> Path:
    """Create a placeholder provisioning profile.

    The placeholder is a valid plist that the device will reject (not signed
    by Apple), but it's the correct file structure. The user must replace it
    with a real profile from Apple Developer or use `fastlane match`.
    """
    profiles_dir = Path.home() / ".smart-apple-dev" / "profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)

    profile_path = profiles_dir / f"{name}.mobileprovision"
    profile_uuid = f"{team_id}-{name.upper()}-0000-0000-0000-000000000000"

    plist = {
        "AppIDName": name,
        "ApplicationIdentifierPrefix": [team_id],
        "CreationDate": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "DeveloperCertificates": [],
        "Entitlements": {
            "application-identifier": f"{team_id}.{bundle_id}",
            "keychain-access-groups": [f"{team_id}.*"],
        },
        "ExpirationDate": datetime(2027, 1, 1, tzinfo=timezone.utc),
        "Name": name,
        "ProvisionedDevices": device_ids or [],
        "TeamIdentifier": [team_id],
        "TeamName": "YOUR_TEAM_NAME",
        "TimeToLive": 365,
        "UUID": profile_uuid,
        "Version": 1,
        "ProvisionsAllDevices": not (device_ids or []),
    }

    with open(profile_path, "wb") as f:
        plistlib.dump(plist, f)

    return profile_path


# ============================================================
# Module-level convenience
# ============================================================

def sign_artifact(artifact: Path, config: ProjectConfig,
                  identity: str | None = None,
                  provisioning_profile: Path | None = None,
                  entitlements: Path | None = None,
                  mode: str = "ad-hoc") -> SignResult:
    """Sign an artifact (.app or .ipa).

    Convenience function for the CLI.
    """
    signer = Signer(config)
    return signer.sign(
        artifact, config,
        mode=mode,
        identity=identity,
        provisioning_profile=provisioning_profile,
        entitlements=entitlements,
    )


def _is_ios_app(app_path: Path) -> bool:
    """Detect if a .app is iOS (vs macOS) by looking at Info.plist."""
    # iOS: Info.plist at root
    ios_plist = app_path / "Info.plist"
    # macOS: Info.plist under Contents/
    macos_plist = app_path / "Contents" / "Info.plist"
    return ios_plist.exists() and not macos_plist.exists()
