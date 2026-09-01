"""Tool registry: wrap the existing CLI commands as agent-callable tools."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ..core.config import (
    ProjectConfig, find_project_root, load_config,
    get_platform, ensure_dirs, get_sdk_dir, get_tool_dir,
)
from ..core.sdk import list_installed_sdks, list_available_sdks, install_sdk
from ..build.provider import get_provider, get_registry
from ..sign import sign_artifact, package_ipa, verify_ipa
from ..device import list_devices, install_ipa
from ..doctor import run_checks


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    handler: Callable[..., str]

    def to_openai_tool(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


SHELL_ALLOWLIST: set[str] = {
    "ls", "cat", "head", "tail", "wc", "file",
    "grep", "find", "which", "whereis",
    "clang", "clang++", "cc", "gcc", "g++", "make", "cmake", "ld", "lld",
    "cargo", "rustc", "go", "swift", "xcrun",
    "xtool", "ldid", "codesign", "otool", "lipo",
    "idevice_id", "ideviceinfo", "ideviceinstaller", "idevicedebug",
    "git",
    "echo", "pwd", "date", "uname", "arch", "env",
    "tar", "zip", "unzip", "gzip",
    "curl", "wget", "jq", "python3", "node",
}

SHELL_BLOCKLIST_PATTERNS: list[str] = [
    "rm -rf /", "rm -rf ~", "rm -rf *",
    ":(){:|:&};:",
    "dd if=", "mkfs", "fdisk",
    "shutdown", "reboot", "halt", "poweroff",
    "passwd", "userdel", "useradd", "visudo",
]


def check_shell_safe(cmd: str) -> tuple:
    cmd = cmd.strip()
    if not cmd:
        return False, "Empty command"
    for pattern in SHELL_BLOCKLIST_PATTERNS:
        if pattern in cmd:
            return False, f"Blocked pattern: {pattern!r}"
    try:
        first = shlex.split(cmd)[0]
    except ValueError:
        return False, "Could not parse command"
    first_base = os.path.basename(first)
    if first_base not in SHELL_ALLOWLIST:
        return False, f"Command {first_base!r} not in allowlist"
    return True, "ok"


def tool_build(args: dict) -> str:
    target = args.get("target", "ios")
    release = bool(args.get("release", False))
    provider_name = args.get("provider")

    root = find_project_root()
    if root is None:
        return "Error: No smartapple.toml found. Run 'smart-apple-dev init' first."

    config = load_config(root)
    if target:
        config.target = target
    prov = get_provider(provider_name)
    available, reason = prov.is_available()
    if not available:
        return f"Error: Provider {prov.name} not available: {reason}"

    result = prov.build(root, config, target=config.target, release=release)
    out = [
        f"Provider: {prov.name}",
        f"Target: {config.target}",
        f"Release: {release}",
        f"Success: {result.success}",
    ]
    if result.artifact:
        out.append(f"Artifact: {result.artifact}")
    if result.duration_seconds:
        out.append(f"Duration: {result.duration_seconds:.1f}s")
    if result.errors:
        out.append(f"Errors: {result.errors[:3]}")
    if not result.success:
        return "\n".join(out) + "\n\n" + (result.output or "")[:500]
    return "\n".join(out)


def tool_sign(args: dict) -> str:
    mode = args.get("mode", "ad-hoc")
    identity = args.get("identity")
    profile = args.get("profile")
    package = bool(args.get("package_ipa", False))

    root = find_project_root()
    if root is None:
        return "Error: No smartapple.toml found."

    config = load_config(root)
    build_dir = root / "build"
    if not build_dir.exists():
        return "Error: No build directory. Run build first."

    apps = sorted(build_dir.rglob("*.app"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not apps:
        return "Error: No .app found. Run build first."
    app = apps[0]

    profile_path = Path(profile) if profile else None
    result = sign_artifact(app, config, identity=identity,
                           provisioning_profile=profile_path, mode=mode)
    out = [f"App: {app}", f"Mode: {mode}", f"Signed: {result.signed}"]
    if result.warnings:
        out.append("Warnings:")
        for w in result.warnings:
            out.append(f"  - {w}")
    if not result.success:
        out.append("Errors:")
        for e in result.errors:
            out.append(f"  - {e}")
        return "\n".join(out)
    out.append(f"Output: {result.artifact_path}")
    if package:
        ipa = package_ipa(result.artifact_path)
        out.append(f"IPA: {ipa} ({ipa.stat().st_size:,} bytes)")
    return "\n".join(out)


def tool_install(args: dict) -> str:
    device_udid = args.get("device_udid")

    devices = list_devices()
    if not devices:
        return "Error: No iOS devices found. Connect one via USB."

    target = device_udid or devices[0].udid
    root = find_project_root()
    if root is None:
        return "Error: No project root."

    ipa = None
    for cand in sorted(root.rglob("*.ipa"), key=lambda p: p.stat().st_mtime, reverse=True):
        ipa = cand
        break

    if ipa is None:
        return f"Error: No .ipa found in {root}. Build and sign first."

    if install_ipa(ipa, target):
        return f"Installed {ipa.name} to {target}"
    return f"Install failed. Try: ideviceinstaller -u {target} -i {ipa}"


def tool_doctor(args: dict) -> str:
    report = run_checks()
    lines = [f"Platform: {report.platform} / {report.arch}"]
    lines.append(f"SDKs installed: {report.sdk_count}")
    lines.append(f"Devices connected: {report.device_count}")
    if report.missing_required:
        lines.append(f"Missing REQUIRED: {len(report.missing_required)}")
        for c in report.missing_required:
            lines.append(f"  - {c.name}: {c.install_hint}")
    if report.missing_optional:
        lines.append(f"Missing optional: {len(report.missing_optional)}")
    return "\n".join(lines)


def tool_sdk_list(args: dict) -> str:
    installed = list_installed_sdks()
    available = list_available_sdks()
    lines = ["Installed:"]
    for s in installed:
        lines.append(f"  {s.platform} {s.version} -> {s.path}")
    if not installed:
        lines.append("  (none)")
    lines.append("\nAvailable for download:")
    for a in available:
        lines.append(f"  {a['platform']} {a['version']}")
    return "\n".join(lines)


def tool_read_file(args: dict) -> str:
    path = args.get("path")
    if not path:
        return "Error: 'path' is required"
    p = Path(path)
    if not p.exists():
        return f"Error: {path} does not exist"
    if not p.is_file():
        return f"Error: {path} is not a file"
    try:
        return p.read_text()
    except UnicodeDecodeError:
        return f"Error: {path} is not a text file"
    except Exception as e:
        return f"Error reading {path}: {e}"


def tool_write_file(args: dict) -> str:
    path = args.get("path")
    content = args.get("content", "")
    if not path:
        return "Error: 'path' is required"
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"Wrote {len(content)} bytes to {p}"


def tool_run_shell(args: dict) -> str:
    cmd = args.get("command", "")
    cwd = args.get("cwd")

    safe, reason = check_shell_safe(cmd)
    if not safe:
        return f"Error: Command not allowed: {reason}"

    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd,
            capture_output=True, text=True, timeout=60,
        )
        out = []
        if result.stdout:
            out.append(result.stdout)
        if result.stderr:
            out.append(f"[stderr]\n{result.stderr}")
        out.append(f"[exit code: {result.returncode}]")
        return "\n".join(out).strip()
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 60 seconds"
    except Exception as e:
        return f"Error: {e}"


def tool_provider_list(args: dict) -> str:
    reg = get_registry()
    lines = []
    for p in reg.list_all():
        available, reason = p.is_available()
        mark = "OK" if available else "NO"
        lines.append(f"[{mark}] {p.name}: {p.description}")
        if not available:
            lines.append(f"     {reason}")
        caps = p.capabilities()
        lines.append(f"     build={caps.build} sign={caps.sign} install={caps.install} upload={caps.upload}")
    return "\n".join(lines)


def tool_ask_user(args: dict) -> str:
    return f"Asked user: {args.get('question', '')}"


def _build_tool_registry() -> dict:
    return {
        "build": Tool(
            name="build",
            description="Build the current smart-apple-dev project. Returns success/failure and the artifact path.",
            parameters={
                "type": "object",
                "properties": {
                    "target": {"type": "string", "enum": ["ios", "ios-simulator", "macos", "catalyst", "watchos", "tvos"], "description": "Build target (default: from smartapple.toml)"},
                    "release": {"type": "boolean", "description": "Build in release mode (default: false)"},
                    "provider": {"type": "string", "description": "Build provider name (default: auto-detect)"},
                },
            },
            handler=tool_build,
        ),
        "sign": Tool(
            name="sign",
            description="Sign the built .app bundle. Default mode is ad-hoc (no certificate).",
            parameters={
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "enum": ["ad-hoc", "identity", "skip"], "description": "Signing mode (default: ad-hoc)"},
                    "identity": {"type": "string", "description": "Apple developer identity (for mode=identity)"},
                    "profile": {"type": "string", "description": "Path to .mobileprovision (iOS only)"},
                    "package_ipa": {"type": "boolean", "description": "After signing, also package as .ipa"},
                },
            },
            handler=tool_sign,
        ),
        "install": Tool(
            name="install",
            description="Install the .ipa to a connected iOS device via libimobiledevice.",
            parameters={"type": "object", "properties": {"device_udid": {"type": "string", "description": "Target device UDID (default: first device found)"}}},
            handler=tool_install,
        ),
        "doctor": Tool(
            name="doctor",
            description="Check the local toolchain: which tools are present, which are missing.",
            parameters={"type": "object", "properties": {}},
            handler=tool_doctor,
        ),
        "sdk_list": Tool(
            name="sdk_list",
            description="List installed Apple SDKs and available versions.",
            parameters={"type": "object", "properties": {}},
            handler=tool_sdk_list,
        ),
        "read_file": Tool(
            name="read_file",
            description="Read the contents of a file.",
            parameters={"type": "object", "properties": {"path": {"type": "string", "description": "Absolute path to the file"}}, "required": ["path"]},
            handler=tool_read_file,
        ),
        "write_file": Tool(
            name="write_file",
            description="Write text content to a file.",
            parameters={"type": "object", "properties": {"path": {"type": "string", "description": "Absolute path"}, "content": {"type": "string", "description": "Text content"}}, "required": ["path", "content"]},
            handler=tool_write_file,
        ),
        "run_shell": Tool(
            name="run_shell",
            description="Run a shell command. Subject to a safety allowlist of common dev tools.",
            parameters={"type": "object", "properties": {"command": {"type": "string", "description": "The command to run"}, "cwd": {"type": "string", "description": "Working directory"}}, "required": ["command"]},
            handler=tool_run_shell,
        ),
        "provider_list": Tool(
            name="provider_list",
            description="List available build providers.",
            parameters={"type": "object", "properties": {}},
            handler=tool_provider_list,
        ),
        "ask_user": Tool(
            name="ask_user",
            description="Ask the user a question when clarification is needed.",
            parameters={"type": "object", "properties": {"question": {"type": "string", "description": "The question to ask"}, "options": {"type": "array", "items": {"type": "string"}, "description": "Optional choices"}}, "required": ["question"]},
            handler=tool_ask_user,
        ),
    }


_TOOLS = None


def get_tools() -> dict:
    global _TOOLS
    if _TOOLS is None:
        _TOOLS = _build_tool_registry()
    return _TOOLS


def get_tool(name: str):
    return get_tools().get(name)


def tool_schemas_for_llm() -> list:
    return [t.to_openai_tool() for t in get_tools().values()]
