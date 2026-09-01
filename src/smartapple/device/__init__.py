"""Device management — wraps libimobiledevice."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..build.orchestrator import run_cmd
from ..core.config import check_tool


@dataclass
class Device:
    """An iOS device."""
    udid: str
    name: str = ""
    product: str = ""
    ios_version: str = ""
    connection: str = "usb"  # usb, wifi, unknown

    def to_dict(self) -> dict[str, Any]:
        return {"udid": self.udid, "name": self.name, "product": self.product,
                "ios_version": self.ios_version, "connection": self.connection}


def list_devices() -> list[Device]:
    """List connected iOS devices using libimobiledevice."""
    idevice = check_tool("idevice_id")
    if idevice is None:
        idevice = check_tool("idevicepair")

    if idevice is None:
        return []  # No libimobiledevice; return empty silently. Doctor reports this.

    # List devices
    exit_code, stdout, stderr = run_cmd([idevice, "-l"], timeout=10)
    if exit_code != 0:
        return []

    devices = []
    for line in stdout.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        udid = line

        # Get device info
        name = _get_device_name(udid)
        product = _get_device_product(udid)
        ios_version = _get_device_version(udid)

        devices.append(Device(
            udid=udid,
            name=name or udid,
            product=product or "Unknown",
            ios_version=ios_version or "Unknown",
        ))

    return devices


def _get_device_name(udid: str) -> str:
    """Get device name."""
    tool = check_tool("ideviceinfo")
    if tool is None:
        return ""
    exit_code, stdout, _ = run_cmd([tool, "-u", udid, "-k", "DeviceName"], timeout=5)
    return stdout.strip() if exit_code == 0 else ""


def _get_device_product(udid: str) -> str:
    """Get device product name."""
    tool = check_tool("ideviceinfo")
    if tool is None:
        return ""
    exit_code, stdout, _ = run_cmd([tool, "-u", udid, "-k", "ProductType"], timeout=5)
    return stdout.strip() if exit_code == 0 else ""


def _get_device_version(udid: str) -> str:
    """Get iOS version."""
    tool = check_tool("ideviceinfo")
    if tool is None:
        return ""
    exit_code, stdout, _ = run_cmd([tool, "-u", udid, "-k", "ProductVersion"], timeout=5)
    return stdout.strip() if exit_code == 0 else ""


def install_ipa(ipa_path: Path, device_udid: str | None = None) -> bool:
    """Install an .ipa to a device."""
    # Find device
    devices = list_devices()
    if not devices:
        print("No devices found. Connect an iOS device and try again.")
        return False

    if device_udid is None:
        device_udid = devices[0].udid

    # Find matching device
    target = None
    for d in devices:
        if d.udid == device_udid:
            target = d
            break
    if target is None:
        print(f"Device {device_udid} not found.")
        return False

    # Install
    install_app = check_tool("ideviceinstaller")
    if install_app is None:
        print("ideviceinstaller not found. Install with: apt-get install libimobiledevice")
        return False

    exit_code, stdout, stderr = run_cmd(
        [install_app, "-u", device_udid, "-i", str(ipa_path)],
        timeout=120,
    )
    return exit_code == 0


def launch_app(bundle_id: str, device_udid: str | None = None) -> bool:
    """Launch an app on a device."""
    devices = list_devices()
    if not devices:
        print("No devices found.")
        return False

    if device_udid is None:
        device_udid = devices[0].udid

    launch = check_tool("idevicediagnostics")
    if launch is None:
        # Try alternative
        launch = check_tool("ideviceinstaller")

    if launch is None:
        print("No device tool found for launching.")
        return False

    # Use the launch tool we actually found (idevicediagnostics preferred)
    exit_code, stdout, stderr = run_cmd(
        [launch, "-u", device_udid, "launch", bundle_id],
        timeout=10,
    )
    return exit_code == 0


def get_device_info(udid: str) -> Device | None:
    """Get info for a specific device."""
    devices = list_devices()
    for d in devices:
        if d.udid == udid:
            return d
    return None