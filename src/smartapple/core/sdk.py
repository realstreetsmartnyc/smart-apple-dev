"""SDK extraction and management for smart-apple-dev."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import get_sdk_dir, get_platform


@dataclass
class SdkInfo:
    """Information about an extracted SDK."""
    version: str
    platform: str  # iphoneos, macosx
    path: Path
    sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"version": self.version, "platform": self.platform,
                "path": str(self.path), "sha256": self.sha256}

    @classmethod
    def from_dict(cls, d: dict) -> "SdkInfo":
        return cls(version=d["version"], platform=d["platform"],
                   path=Path(d["path"]), sha256=d.get("sha256", ""))


SDK_VERSIONS = {
    "iphoneos": {
        "17.2": "https://github.com/tpoechtrager/osxcross/releases/download/sdk-17.2/iPhoneOS17.2.sdk.tar.xz",
        "18.0": "https://github.com/tpoechtrager/osxcross/releases/download/sdk-18.0/iPhoneOS18.0.sdk.tar.xz",
    },
    "macosx": {
        "14.0": "https://github.com/tpoechtrager/osxcross/releases/download/sdk-14.0/macosx14.0.sdk.tar.xz",
        "15.0": "https://github.com/tpoechtrager/osxcross/releases/download/sdk-15.0/macosx15.0.sdk.tar.xz",
    },
}


def list_available_sdks() -> list[dict]:
    """List available SDK versions for download."""
    result = []
    for platform, versions in SDK_VERSIONS.items():
        for version, url in versions.items():
            result.append({"platform": platform, "version": version, "url": url})
    return result


def list_installed_sdks() -> list[SdkInfo]:
    """List SDKs already extracted locally."""
    sdk_dir = get_sdk_dir()
    index_file = sdk_dir / "index.json"
    if not index_file.exists():
        return []
    with open(index_file) as f:
        data = json.load(f)
    return [SdkInfo.from_dict(d) for d in data]


def get_sdk(platform: str = "iphoneos", version: str | None = None) -> Path:
    """Get the path to an installed SDK, downloading if needed."""
    installed = list_installed_sdks()
    matching = [s for s in installed if s.platform == platform]
    if version:
        matching = [s for s in matching if s.version == version]
    if matching:
        # Prefer newest
        matching.sort(key=lambda s: s.version, reverse=True)
        return matching[0].path
    raise SdkError(f"No SDK installed for {platform}/{version or 'any'}. "
                   f"Run 'smart-apple-dev sdk install' first.")


def install_sdk(platform: str, version: str) -> SdkInfo:
    """Download and extract an Apple SDK."""
    if platform not in SDK_VERSIONS:
        raise SdkError(f"Unknown SDK platform: {platform}. "
                       f"Available: {list(SDK_VERSIONS.keys())}")
    if version not in SDK_VERSIONS[platform]:
        raise SdkError(f"Unknown SDK version: {version}. "
                       f"Available: {list(SDK_VERSIONS[platform].keys())}")

    url = SDK_VERSIONS[platform][version]
    sdk_dir = get_sdk_dir()
    archive_name = f"{platform}{version}.sdk.tar.xz"
    archive_path = sdk_dir / archive_name

    print(f"Downloading {platform} {version} SDK...")
    subprocess.run(["curl", "-L", "-o", str(archive_path), url], check=True)

    # Compute hash
    sha = hashlib.sha256()
    with open(archive_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha.update(chunk)
    sha256 = sha.hexdigest()

    # Extract
    extract_dir = sdk_dir / f"{platform}-{version}.sdk"
    extract_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "r:xz") as tar:
        tar.extractall(extract_dir)

    # Find the actual .sdk directory inside
    sdk_path = None
    for item in extract_dir.iterdir():
        if item.is_dir() and item.name.endswith(".sdk"):
            sdk_path = item
            break
    if sdk_path is None:
        # Maybe it's directly the SDK
        sdk_path = extract_dir

    # Update index
    index_file = sdk_dir / "index.json"
    index = []
    if index_file.exists():
        with open(index_file) as f:
            index = json.load(f)
    # Remove old entries for same platform/version
    index = [e for e in index if not (e["platform"] == platform and e["version"] == version)]
    index.append({"version": version, "platform": platform,
                  "path": str(sdk_path), "sha256": sha256})
    with open(index_file, "w") as f:
        json.dump(index, f, indent=2)

    # Cleanup archive
    archive_path.unlink()

    print(f"SDK installed: {sdk_path}")
    return SdkInfo(version=version, platform=platform, path=sdk_path, sha256=sha256)


def extract_sdk_from_macos(source_path: Path, platform: str = "iphoneos",
                           version: str = "18.0") -> SdkInfo:
    """Extract SDK from a local Mac Xcode installation.
    
    This is the one-time setup step. On a Mac, the SDK is already present.
    This function copies it for use on Linux/Windows.
    """
    sdk_dir = get_sdk_dir()
    
    # Find the SDK on the Mac
    if platform == "iphoneos":
        candidates = [
            Path("/Applications/Xcode.app/Contents/Developer/Platforms/iPhoneOS.platform/SDK"),
            Path("/Applications/Xcode.app/Contents/Developer/Platforms/iPhoneOS.platform"),
        ]
    elif platform == "macosx":
        candidates = [
            Path("/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/SDK"),
            Path("/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform"),
        ]
    else:
        raise SdkError(f"Unknown platform: {platform}")

    source = None
    for c in candidates:
        if c.exists():
            source = c
            break
    if source is None:
        raise SdkError(f"Could not find {platform} SDK at expected paths. "
                       f"Is Xcode installed?")

    dest = sdk_dir / f"{platform}-{version}.sdk"
    if dest.exists():
        shutil.rmtree(dest)

    print(f"Copying SDK from {source} to {dest}...")
    shutil.copytree(source, dest)

    # Update index
    index_file = sdk_dir / "index.json"
    index = []
    if index_file.exists():
        with open(index_file) as f:
            index = json.load(f)
    index = [e for e in index if not (e["platform"] == platform and e["version"] == version)]
    index.append({"version": version, "platform": platform, "path": str(dest), "sha256": ""})
    with open(index_file, "w") as f:
        json.dump(index, f, indent=2)

    print(f"SDK extracted: {dest}")
    return SdkInfo(version=version, platform=platform, path=dest)


class SdkError(Exception):
    """SDK-related error."""
    pass