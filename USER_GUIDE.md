# smart-apple-dev User Guide

## Overview

smart-apple-dev is a cross-platform (Linux/Windows) iOS/macOS development toolchain that lets you build, sign, install, and deploy iOS/macOS apps without needing a Mac. It wraps open-source tools (clang + LLD, xtool, ldid, cctools-port, libimobiledevice) and provides a unified CLI for the full pipeline.

## Requirements

- **Linux or WSL2 on Windows**: Linux distributions (Ubuntu, Debian) or Windows Subsystem for Linux 2
- **CMake**, **make**, **tar**, **curl**, **git** (required for Linux builds)
- **clang** and **lld64.lld** (or `lld`) for C/C++/ObjC compilation
- **xtool** for Swift builds (optional, auto-installable)
- **ldid** for signing (optional, build from source on Linux)
- **cctools-port** for codesign (optional, build from source)
- **libimobiledevice** for iOS device communication (optional)
- **Swift/Native toolchains** per language (optional, but needed for CI/testing)

## Quick Start

1. **Install**

   ```bash
   pip install smart-apple-dev
   ```

   Or from source:

   ```bash
   git clone https://github.com/smart-apple-dev/smart-apple-dev
cd smart-apple-dev
pip install -e ".[dev]"  # includes testing and linting tools
   ```

2. **Check your toolchain**

   ```bash
   smart-apple-dev doctor
   ```

   Follow any missing required tool hints. Optional tools (like `xtool`, `ldid`, `cctools`) can be auto-installed where supported.

3. **Create a project**

   ```bash
   smart-apple-dev init my-app --lang objc
cd my-app
   ```

   Available languages: `swift`, `objc`, `cpp`, `rust`, `go`, `kotlin`. If you omit `--lang`, defaults to Swift.

4. **Build**

   ```bash
   # macOS app (works on Linux with a MacOSX SDK)
   smart-apple-dev build --target macos

   # iOS/macOS app
   smart-apple-dev build

   # Release build
   smart-apple-dev build --release
   ```

   Result: `build/ios/MyApp.app` (or `build/macos/MyApp.app`)

5. **Sign (ad‑hoc or identity)**

   ```bash
   # Ad‑hoc signing (default, no certificate needed)
   smart-apple-dev sign

   # Identity signing (requires Apple Developer certificate + ldid)
   smart-apple-dev sign --mode identity --identity "iPhone Developer: Your Name (ABC123)"
   ```

   `.ipa` packaging:

   ```bash
   smart-apple-dev sign --to-ipa
   ```

6. **Install to an iOS device**

   ```bash
   smart-apple-dev install --ipa my-app.ipa
   ```

   Requires a connected iOS device and libimobiledevice tools.

7. **App Store Connect upload**

   ```bash
   smart-apple-dev store upload my-app.ipa --username you@example.com --password your-app-specific-password
   smart-apple-dev store submit my-app --username you@example.com
   ```

   Requires Fastlane or altool installed.

8. **Agent REPL**

   ```bash
   smart-apple-dev agent
   ```

   Enter commands like `build`, `sign`, `install`, `devices`, `info` — the agent can use an LLM provider (Anthropic, OpenAI, Ollama) or run deterministic plans (no API keys required).

## Reference: All CLI Commands

### smart-apple-dev init

Scaffolds a new project.

```
smart-apple-dev init <name> [--lang swift|objc|cpp|rust|go|kotlin] [--bundle-id com.example.name]
```

Creates:
- `smartapple.toml` config
- Language‑specific template (`.swift`, `.m`, `.cpp`, etc.)
- `build/` directory structure

### smart-apple-dev build

Builds the project using the language‑specific backend.

```
smart-apple-dev build [--target ios|ios-simulator|macos|catalyst] [--release] [--provider local|ssh]
```

Output: `build/<target>/<name>.app` (Mach‑O bundle).

### smart-apple-dev sign

Signs a built `.app` bundle and optionally packages it as an `.ipa`.

```
smart-apple-dev sign [--mode ad-hoc|identity|skip] [--identity <name>] [--profile <mobileprovision>]
                    [--entitlements <plist>] [--ipa] [--target <target>]
```

Modes:
- `ad‑hoc`: ldid/codesign with no certificate (no certs required)
- `identity`: real Apple Developer certificate (requires `ldid` with cert)
- `skip`: no signing (just package)

### smart-apple-dev install

Builds + signs + packages + installs to a connected iOS device.

```
smart-apple-dev install [--device <udid>] [--ipa <ipa>]
```

If `--ipa` omitted, runs the full pipeline and installs via `ideviceinstaller`.

### smart-apple-dev devices

Lists connected iOS devices (requires libimobiledevice).

### smart-apple-dev info

Shows system info, project root, SDK installation, and installed providers.

### smart-apple-dev sdk

SDK management:
- `list`: shows installed SDKs
- `install <platform> [--version <ver>]`: downloads a new SDK (iphoneos/macosx)
- `extract --platform iphoneos --version 18.0`: on macOS, packages an SDK tarball that can be moved to Linux

### smart-apple-dev provider

Provider system:
- `list`: shows registered providers and their availability
- `default`: shows the currently selected provider

Available providers:
- `local`: runs everything on this machine (default)
- `ssh`: runs on a remote Mac (requires paramiko and SSH access)

### smart-apple-dev doctor

Diagnoses missing required/optional tools. Auto‑install optional ones with `--install`.

### smart-apple-dev check

Per‑language backend availability check (which tools are missing for each language).

### smart-apple-dev agent

LLM‑driven orchestration with a toolbelt of 10 actions:

| Tool | Description |
|------|-------------|
| build | Run the build pipeline for a project |
| sign | Sign an existing .app or .ipa |
| install | Install an .ipa to a device |
| devices | List connected iOS devices |
| sdk_list | List available SDKs |
| read_file | Read any file in the project (helpful for debugging) |
| write_file | Write a file in the project (e.g., to scaffold a new file) |
| run_shell | Execute a shell command (security allowlist/blocklist) |
| provider_list | List providers and their status |
| ask_user | Ask for interactive user input (must be responded to before continuing) |

The agent can be deterministic (`--provider none`) for reproducible automation, or use an LLM provider (Anthropic, OpenAI, Ollama). See `.env.example` for API key setup.

### smart-apple-dev --version / --help

Print version or show full CLI help.

## File Layout (after init)

```
my-app/
├── smartapple.toml               # project config
├── templates/                    # language‑specific starter files
│   ├── objc/
│   │   ├── main.m
│   │   └── smartapple.toml
│   ├── cpp/
│   │   ├── main.cpp
│   │   └── smartapple.toml
│   └── ... (other languages)
├── build/                        # output directory
│   ├── ios/
│   │   └── MyApp.app           # Mach‑O bundle (clang + LLD + SDK)
│   └── macos/
│       └── MyApp.app
└── Makefile, CMakeLists.txt, etc.   # language‑specific build files
```

## Troubleshooting

### “Error: click is required” / "Error: ldid not found”

Install missing optional tools with `smart-apple-dev doctor --install`. Required tools (clang, make, tar, curl, git) must be present in PATH.

### “Error: No smartapple.toml found”

Run `smart-apple-dev init <name>` inside the desired project directory.

### “Error: SDK not installed”

Run `smart-apple-dev sdk install macosx 11.3`. For iOS, extract on macOS (`smart-apple-dev sdk extract --platform iphoneos`) and move the tarball to Linux.

### “Error: No signing tool found”

Ad‑hoc signing works without `ldid`. For identity signing, you need `ldid`. Build from source on Linux:

```bash
git clone https://github.com/saurik/ldid.git
cd ldid
g++ -I . -o ldid ldid.cpp util.cpp -lcrypto -lpthread
cp ldid ~/.smart-apple-dev/tools/ldid
export PATH=$HOME/.smart-apple-dev/tools:$PATH
```

### “Error: libimobiledevice not found”

On Ubuntu/Debian: `sudo apt-get install libimobiledevice-dev usbmuxd`. May need additional kernel modules for USB communication.

### “Agent loop fails to call tools”

Agent tools are CLI wrappers. Ensure the CLI command `smart-apple-dev` is in PATH after installation (`pip install smart-apple-dev`).

### “Fastlane not found”

Install Fastlane with `brew install fastlane` (macOS) or download from https://download.fastlane.tools. Fastlane is required for App Store Connect upload and submit.

## Logging & Output

By default, smart-apple-dev outputs human‑readable progress and results. Use `--json` to get machine‑parsable output (e.g., `smart-apple-dev build --json`).

The `--quiet` flag silences thinking/tool output (agent mode) or suppresses warnings.

## Environment Variables

Copy `.env.example` to `.env` in your project root or home directory:

```bash
cp .env.example .env
```

Variables include LLM API keys, Fastlane credentials, and remote SSH access for the `ssh` provider.

## Advanced: SSH provider

Run builds on a remote Mac with SSH:

```bash
# First, on the remote Mac:
#   mkdir -p ~/.ssh && ssh-keygen -t rsa -N "" && ssh-copy-id user@remote-mac
#   sudo apt-get install clang lld make tar curl git cmake pkg-config
#   sudo apt-get install lldcctools-port ldid

# On Linux:
smart-apple-dev init my-app --lang swift
smart-apple-dev build --provider ssh --target macos
```

You need to set environment variables:

```bash
export SSH_HOST=remote-mac.local
export SSH_USERNAME=user
export SSH_KEY_PATH=~/.ssh/id_rsa
```

The `ssh` provider will auto‑install paramiko if missing (pip install paramiko).

## Further Reading

- [ARCHITECTURE.md](ARCHITECTURE.md) – design and component rationale
- [MAP.md](MAP.md) – roadmap and decisions (D1‑D15)
- GitHub repository: https://github.com/smart-apple-dev/smart-apple-dev

## License

MIT
