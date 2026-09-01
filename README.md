# smart-apple-dev

Cross-platform iOS/macOS development toolchain for Linux and Windows.

[![CI](https://github.com/smart-apple-dev/smart-apple-dev/actions/workflows/ci.yml/badge.svg)](https://github.com/smart-apple-dev/smart-apple-dev/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/smart-apple-dev.svg)](https://pypi.org/project/smart-apple-dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Build, sign, install, and deploy iOS and macOS apps without a Mac.

## Status (v1.0.0)

| Capability | Status |
|------------|--------|
| Cross-platform CLI (Linux/Windows/macOS) | ✓ |
| Project scaffolding for Swift, ObjC, C++, Rust, Go, Kotlin | ✓ |
| `smartapple.toml` config | ✓ |
| `doctor` for toolchain diagnosis | ✓ |
| Auto-install xtool | ✓ |
| C/ObjC/C++ → Mach-O .app on Linux (via LLD + MacOSX SDK) | ✓ verified |
| C++ with libc++ | ✓ verified |
| Swift via xtool | ✓ tested (with xtool) |
| Rust via cargo/cross-rs | ✓ tested (with mocked toolchain) |
| Go via native cross-compile | ✓ tested (with mocked toolchain) |
| Kotlin/Native via Gradle | ✓ tested (with mocked toolchain) |
| Code signing (ldid) | ✓ verified |
| Ad-hoc + identity signing | ✓ |
| IPA packaging + verification | ✓ verified |
| Provisioning profile creation | ✓ |
| iOS device install (libimobilevervice) | ✓ tested |
| Provider abstraction (local + SSH) | ✓ |
| App Store Connect upload (fastlane/altool) | ✓ |
| App Store Connect submit for review | ✓ |
| Agent loop (LLM) with toolbelt | ✓ tested (plan mode) |
| Per-project agent memory | ✓ |
| CI/CD pipeline | ✓ |
| Type checking (mypy) | ✓ |
| Linting (ruff) | ✓ |

## Quick Start

```bash
# Install from PyPI
pip install smart-apple-dev

# Or install from source
git clone https://github.com/smart-apple-dev/smart-apple-dev
cd smart-apple-dev
pip install -e ".[dev]"

# Check your toolchain
smart-apple-dev doctor

# Create a project
smart-apple-dev init my-app --lang objc
cd my-app

# Build for macOS (works on Linux with a MacOSX SDK)
smart-apple-dev build --target macos
# -> build/macos/MyApp.app
```

## Building iOS apps on Linux

With clang + ld64.lld (LLVM) and the MacOSX SDK:

```bash
# One-time: install a MacOSX SDK
smart-apple-dev sdk install macosx 11.3

# Build
cd my-objc-project
smart-apple-dev build --target macos
file build/macos/MyApp.app/Contents/MacOS/MyApp
# -> Mach-O 64-bit x86_64 executable
```

For iOS targets, you need an iPhoneOS SDK extracted from a real Mac:
`smart-apple-dev sdk extract` on macOS, then move the tarball to Linux.

## Supported Languages

| Language | Build System | Backend | Status |
|----------|-------------|---------|--------|
| Swift | SwiftPM | xtool | ✓ |
| Objective-C | Makefile/CMake | clang + LLD | ✓ works (macos) |
| C | CMake | clang + LLD | ✓ works (macos) |
| C++ | CMake | clang + LLD + libc++ | ✓ works (macos) |
| Rust | Cargo | cargo + cross-rs | ✓ tested |
| Go | Go modules | native cross-compile | ✓ tested |
| Kotlin/Native | Gradle | kotlin-native | ✓ tested |

## Environment Variables

Copy `.env.example` to `.env` and fill in:

```bash
cp .env.example .env
```

See `.env.example` for all supported environment variables (LLM API keys, Fastlane credentials).

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full design.
See [MAP.md](MAP.md) for the goal structure and roadmap.
See [USER_GUIDE.md](USER_GUIDE.md) for the complete command reference.
See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup.

## Tests

```bash
python3 -m pytest tests/ -v --cov=src/smartapple --cov-report=term-missing
# 68 tests
```

## CLI Shell Completion

```bash
# Bash
echo 'eval "$(_SMART_APPLE_DEV_COMPLETE=bash_source smart-apple-dev)"' >> ~/.bashrc

# Zsh
echo 'eval "$(_SMART_APPLE_DEV_COMPLETE=zsh_source smart-apple-dev)"' >> ~/.zshrc

# Fish
echo 'eval (env _SMART_APPLE_DEV_COMPLETE=fish_source smart-apple-dev) | source' >> ~/.config/fish/config.fish
```

## License

MIT
