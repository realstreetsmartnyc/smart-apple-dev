# smart-apple-dev — Architecture & Build Plan

## Architecture

```
smart-apple-dev (Python CLI, cross-platform)
│
├── core/
│   ├── config.py       # Project config (smartapple.toml)
│   ├── sdk.py          # SDK extraction & management
│   └── logger.py       # Structured logging
│
├── build/
│   ├── orchestrator.py  # Language-agnostic build dispatcher
│   ├── swift.py         # SwiftPM backend (wraps xtool)
│   ├── cpp.py           # C/C++/ObjC backend (wraps clang + LLD)
│   ├── rust.py          # Rust backend (wraps cargo + cross-rs)
│   ├── go.py            # Go backend (native cross-compile)
│   ├── kotlin.py        # Kotlin/Native backend (gradle)
│   ├── provider.py      # Provider system (local, SSH)
│   └── ssh_provider.py  # SSH provider (remote Mac)
│
├── sign/
│   └── __init__.py      # Codesign wrapper (ldid, codesign) + IPA packaging
│
├── device/
│   └── __init__.py      # Device discovery + install + launch (libimobiledevice)
│
├── store/
│   └── __init__.py      # App Store Connect (fastlane, altool)
│
├── agent/
│   ├── __init__.py      # Agent module
│   ├── llm.py           # LLM provider abstraction
│   ├── tools.py         # Agent tool registry
│   └── loop.py          # ReAct-style agent loop
│
├── cli/
│   ├── __init__.py      # CLI entry point
│   └── app.py           # Main CLI app (Click-based, 12 commands)
│
├── templates/
│   ├── swift/           # Swift project template
│   ├── objc/           # Objective-C project template
│   ├── cpp/            # C++ project template
│   ├── rust/           # Rust project template
│   ├── go/             # Go project template
│   └── kotlin/         # Kotlin/Native project template
│
└── doctor.py            # Toolchain diagnostics
```

> **Note:** For MVP simplicity, signing, device, and store modules are consolidated in single `__init__.py` files. They can be split into submodules later (e.g., `sign/signer.py`, `device/manager.py`) if needed.

## Technology Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| CLI | Python 3.11+ + Click | Cross-platform, fast to build, existing tools are Python-wrappable |
| Swift backend | xtool (Rust) | Mature, ~5K stars, handles SwiftPM + signing + install |
| C/C++/ObjC backend | clang + LLD | LLVM toolchain, native Mach-O generation |
| Rust backend | cargo + cross-rs | Native Rust iOS target support |
| Go backend | native cross-compile | Go's built-in `GOOS=ios GOARCH=arm64` |
| Kotlin/Native backend | Kotlin/Native via Gradle | Kotlin Multiplatform with iOS target |
| Signing | ldid + cctools-port | Open-source codesign replacement |
| Device | libimobiledevice | Cross-platform iOS device communication |
| App Store Connect | Fastlane + altool | Industry-standard tooling |
| Config | TOML (smartapple.toml) | Human-readable, well-supported |
| LLM Agent | Anthropic, OpenAI, Ollama, or None | Flexible LLM provider abstraction |

## Build Pipeline (per language)

```
smart-apple-dev build [--lang swift|objc|cpp|rust|go|kotlin]
│
├── 1. SDK CHECK
│   └── Verify Apple SDK is available (extract if needed)
│
├── 2. LANGUAGE DISPATCH
│   ├── Swift → xtool build
│   ├── ObjC/C/C++ → clang + LLD
│   ├── Rust → cargo build --target aarch64-apple-ios
│   ├── Go → GOOS=ios GOARCH=arm64 go build
│   └── Kotlin → kotlin-native iosArm64
│
├── 3. SIGNING
│   └── ldid + cctools-port codesign
│
├── 4. IPA PACKAGING
│   └── zip + payload structure
│
└── 5. OUTPUT
    └── .ipa file ready for install or App Store upload
```

## SDK Extraction Strategy

The Apple SDK (iPhoneOS, macOS) is proprietary and cannot be distributed.
Strategy:
1. User runs `smart-apple-dev sdk extract` on a Mac (one-time)
2. SDK is packaged and stored in `~/.smart-apple-dev/sdk/`
3. On Linux/Windows, SDK is unpacked and used for cross-compilation
4. SDK is versioned — `smart-apple-dev sdk list` shows available versions

This is the same approach osxcross uses, and it's the only legally clean way to get the SDK.

## Signing Architecture

```
Apple Developer Certificate (from Apple)
    │
    ├── ldid (Linux codesign replacement)
    │   └── Signs the binary with the certificate
    │
    ├── Provisioning Profile
    │   └── Contains app ID, capabilities, device list
    │
    └── cctools-port
        └── Provides codesign, ld, other Mach-O tools
```

The signing chain works because:
1. The certificate is issued by Apple (requires Apple Developer account)
2. ldid can sign Mach-O binaries on Linux using the certificate
3. The provisioning profile is embedded in the IPA
4. The device trusts the certificate because it's an Apple-issued dev cert

This is the same mechanism xtool uses, and it works.

## Provider System

```
BuildProvider (ABC)
    ├── LocalProvider       # Runs on this machine (Linux, Windows, macOS)
    └── SSHProvider         # Runs on a remote Mac via SSH
```

The provider system handles *where* the build runs, while the orchestrator handles *what* gets built.

## Agent Architecture

```
AgentConfig
    └── run_agent()
        ├── LLMProvider (ABC)
        │   ├── NoneProvider    # Deterministic plan execution
        │   ├── AnthropicProvider # Claude via API
        │   ├── OpenAIProvider  # GPT via API
        │   └── OllamaProvider  # Local llama
        │
        └── ToolRegistry (10 tools)
            ├── build, sign, install, devices, sdk_list
            ├── read_file, write_file, run_shell
            ├── provider_list, ask_user
            └── check
```

The agent follows a ReAct loop: observe → think → act → repeat, with per-project memory persisted as JSON.