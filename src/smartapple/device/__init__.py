"""Device management — wraps libimobiledevice (iOS) and adb (Android)."""

from __future__ import annotations

from dataclasses import dataclass
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


@dataclass
class AndroidDevice:
    """An Android device or emulator."""
    serial: str
    state: str = "device"  # device, offline, unauthorized, no permissions
    product: str = ""
    model: str = ""
    transport: str = "usb"  # usb, tcp

    def to_dict(self) -> dict[str, Any]:
        return {"serial": self.serial, "state": self.state, "product": self.product,
                "model": self.model, "transport": self.transport}


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


# ============================================================
# Android helpers — wraps the `adb` CLI
# ============================================================

def _adb() -> str | None:
    """Locate the adb binary on PATH."""
    return check_tool("adb")


def list_android_devices() -> list[AndroidDevice]:
    """List connected Android devices and emulators via `adb devices -l`."""
    adb = _adb()
    if adb is None:
        return []  # No adb; doctor reports this.

    exit_code, stdout, _ = run_cmd([adb, "devices", "-l"], timeout=10)
    if exit_code != 0:
        return []

    devices: list[AndroidDevice] = []
    # Skip header line ("List of devices attached")
    for line in stdout.splitlines()[1:]:
        line = line.strip()
        if not line or line.startswith("*"):
            continue

        # adb output format:
        #   <serial>  <state>  <key1>:<value1> <key2>:<value2> ...
        # e.g. "emulator-5554  device product:sdk_gphone64_x86_64 model:Android_SDK_built_for_x86_64"
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, state = parts[0], parts[1]

        kv: dict[str, str] = {}
        for token in parts[2:]:
            if ":" in token:
                k, v = token.split(":", 1)
                kv[k] = v

        transport = "tcp" if serial.startswith(("emulator-", "127.0.0.1", "localhost")) else "usb"
        devices.append(AndroidDevice(
            serial=serial,
            state=state,
            product=kv.get("product", ""),
            model=kv.get("model", ""),
            transport=transport,
        ))
    return devices


def install_apk(apk_path: Path, device_serial: str | None = None,
               *, validate_device: bool = True) -> bool:
    """Install an .apk to an Android device via adb.

    Set ``validate_device=False`` to skip the internal ``adb devices``
    round-trip (useful when the caller has already enumerated devices).
    """
    from .. import ui

    if not apk_path.exists():
        ui.error(f"APK not found: {apk_path}")
        return False

    adb = _adb()
    if adb is None:
        ui.error("adb not found.")
        ui.hint("Install with: apt-get install adb  (or brew install android-platform-tools)")
        return False

    if validate_device:
        devices = list_android_devices()
        if not devices:
            ui.warning("No Android devices found.")
            ui.hint("Connect a device with USB debugging enabled.")
            return False

        if device_serial is None:
            device_serial = devices[0].serial
        else:
            # Validate user-supplied serial
            if not any(d.serial == device_serial for d in devices):
                ui.error(f"Device {device_serial} not found in `adb devices`.")
                return False
    elif device_serial is None:
        ui.error("device_serial is required when validate_device=False")
        return False

    # -r: replace existing install; -t: allow test packages
    exit_code, stdout, stderr = run_cmd(
        [adb, "-s", device_serial, "install", "-r", str(apk_path)],
        timeout=180,
    )

    if exit_code != 0:
        if "INSTALL_FAILED_USER_RESTRICTED" in (stderr or ""):
            ui.error("Install blocked: device disallows installs from this source.")
            ui.hint("Enable USB debugging (Security) -> 'Install via USB' on the device.")
        elif "unauthorized" in (stderr or "").lower():
            ui.error("Device unauthorized.")
            ui.hint("Accept the RSA fingerprint prompt on the device.")
        else:
            ui.error(f"adb install failed: {stderr.strip() or stdout.strip()}")
        return False

    return True


def get_android_device_info(serial: str) -> AndroidDevice | None:
    """Get info for a specific Android device."""
    for d in list_android_devices():
        if d.serial == serial:
            return d
    return None
