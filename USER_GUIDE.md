# smart-apple-dev User Guide

Complete CLI reference for `smart-apple-dev` v1.0.0.

## Installation

```bash
pip install smart-apple-dev
# or isolated:
pipx install smart-apple-dev
```

From source:

```bash
git clone https://github.com/smart-apple-dev/smart-apple-dev
cd smart-apple-dev
pip install -e ".[dev]"
```

**Requirements:** Python 3.11+

## Quick Start

```bash
smart-apple-dev doctor              # diagnose
smart-apple-dev init my-app --lang objc
cd my-app
smart-apple-dev build --target macos
smart-apple-dev sign --ipa          # → build/macos/my-app.ipa
```

## Commands

### `smart-apple-dev init`

Scaffold a project from a language template.

```bash
smart-apple-dev init <name> [--lang <lang>] [--bundle-id com.example.name]
```

Languages: `swift`, `objc`, `cpp`, `rust`, `go`, `kotlin`, plus experimental: `javascript`, `typescript`, `java`, `python`, `csharp`, `godot`, `unity`, `swiftui`, `watchos`, `tvos`, `visionos`, `macos`, `ios`, `metal`, `capacitor`, `expo`, `flutter`, `react-native`, `unreal`, `spritekit`, `scenekit`.

Output: `<name>/smartapple.toml` + language template.

### `smart-apple-dev build`

Build the project declared in `smartapple.toml`.

```bash
smart-apple-dev build [--target ios|ios-simulator|macos|catalyst|android] [--release] [--provider local|ssh|...]
```

- `--target` — platform (default from `smartapple.toml`)
- `--release` — optimized build
- `--provider` — build provider (default: auto-detect, usually `local`)

Output: `build/<target>/` for Apple targets; for `--target android`, the APK is written to
`<project>/build/outputs/apk/<debug|release>/`.

**Android prerequisites:** JDK 17+ and the Android SDK with `platforms;android-34` and
`build-tools;34.0.0` installed. Set `ANDROID_HOME` (or `ANDROID_SDK_ROOT`) to the SDK
location. `smart-apple-dev` shells out to `./gradlew assembleDebug` (or `assembleRelease`
with `--release`).

### `smart-apple-dev sign`

Sign a `.app` and optionally package as `.ipa`.

```bash
smart-apple-dev sign [--mode ad-hoc|identity|skip] [--identity <name>] [--profile <path>] [--entitlements <plist>] [--ipa] [--target <target>]
```

Modes:
- `ad-hoc` — ldid/codesign without Apple identity (default on Linux)
- `identity` — Apple Developer identity (needs cert + provisioning profile)
- `skip` — package only

### `smart-apple-dev install`

Install a built artifact to a connected device. iOS (`.ipa`) uses `ideviceinstaller`;
Android (`.apk`) uses `adb`.

```bash
smart-apple-dev install [--device <udid|serial>] [--ipa <path>] [--apk <path>] [--platform ios|android|auto]
```

- Without `--ipa` / `--apk`, builds first (and signs for Apple targets).
- `--platform auto` (default) picks the platform from `smartapple.toml`'s `target` field.
- iOS requires `libimobiledevice` on Linux.
- Android requires `adb` and a device with USB debugging enabled.

### `smart-apple-dev devices`

List connected iOS and/or Android devices.

```bash
smart-apple-dev devices [--platform all|ios|android]  # default: all
```

### `smart-apple-dev info`

Show platform, project root, tools, and installed SDKs.

```bash
smart-apple-dev info
```

### `smart-apple-dev sdk`

Manage Apple SDKs.

```bash
smart-apple-dev sdk list
smart-apple-dev sdk install --platform macosx --version 11.3
smart-apple-dev sdk extract --platform iphoneos --version 18.0
```

`extract` must run on macOS with Xcode; `install` works anywhere.

### `smart-apple-dev doctor`

Diagnose (and optionally auto-install) required tools.

```bash
smart-apple-dev doctor
smart-apple-dev doctor --install
```

Checks: `clang`, `lld`/`ld`, `ldid`/`codesign`, SDKs, per-language toolchains.

### `smart-apple-dev check`

Show per-language backend availability.

```bash
smart-apple-dev check
```

### `smart-apple-dev provider`

Inspect build providers.

```bash
smart-apple-dev provider list          # all 12 providers + status
smart-apple-dev provider default       # current default

# Named LLM provider instances
smart-apple-dev provider add <base:label> [--base-url URL] [--api-key KEY] [--model NAME] [--description TEXT]
smart-apple-dev provider del <base:label>
smart-apple-dev provider list-instances
```

Examples:

```bash
smart-apple-dev provider add copilot:default --api-key $GITHUB_TOKEN
smart-apple-dev provider add custom:openrouter --base-url https://openrouter.ai/api/v1 --api-key $OR_KEY --model anthropic/claude-3.5-sonnet
smart-apple-dev provider add custom:venice --base-url https://api.venice.ai/api/v1 --api-key $VENICE_KEY
```

Instances are stored in `~/.smart-apple-dev/llm-providers.json`. API keys can use `${ENV_VAR}` references.

### `smart-apple-dev agent`

Run the LLM agent (one-shot or REPL).

```bash
# One-shot
smart-apple-dev agent "build and sign this project"

# With provider selection
smart-apple-dev agent --provider anthropic "add a settings screen"
smart-apple-dev agent --provider ollama "what's the build error?"
smart-apple-dev agent --provider copilot:default "ship it"

# List providers
smart-apple-dev agent --provider list

# Plan-based (deterministic, for CI/testing)
smart-apple-dev agent --provider none --plan plan.json "build and sign"

# REPL (no request → interactive)
smart-apple-dev agent --provider openai
```

Options:
- `--provider, -p` — LLM provider (`auto`, `list`, or `base:label`)
- `--model` — override model
- `--max-iterations` — max loop turns (default 15)
- `--quiet` — less output
- `--plan` — JSON plan for deterministic execution (with `--provider none`)

The agent has 10 tools: `doctor`, `build`, `sign`, `install`, `sdk_list`, `read_file`, `write_file`, `run_shell`, `provider_list`, `ask_user`. Shell access has an allowlist/blocklist for safety.

## Configuration

### `smartapple.toml`

Created by `init`, read by `build`/`sign`:

```toml
[project]
name = "my-app"
language = "objc"
bundle_id = "com.example.my-app"
version = "1.0.0"
build_system = "swiftpm"
min_os = "15.0"
target = "ios"
```

### LLM Provider Config

`~/.smart-apple-dev/llm-providers.json`:

```json
{
  "instances": {
    "copilot:default": {
      "base_url": "https://api.githubcopilot.com",
      "api_key": "${GITHUB_TOKEN}",
      "default_model": "gpt-4o"
    }
  }
}
```

### LLM Providers

21 bases, each with env var for API key:

| Base | Env var | Default model |
|------|---------|---------------|
| `anthropic` | `ANTHROPIC_API_KEY` | claude-3-5-sonnet |
| `openai` | `OPENAI_API_KEY` | gpt-4o |
| `groq` | `GROQ_API_KEY` | llama-3.3-70b |
| `mistral` | `MISTRAL_API_KEY` | mistral-large |
| `together` | `TOGETHER_API_KEY` | llama-3.3-70b |
| `xai` | `XAI_API_KEY` | grok-2 |
| `deepseek` | `DEEPSEEK_API_KEY` | deepseek-chat |
| `perplexity` | `PERPLEXITY_API_KEY` | llama-3.1-sonar-large |
| `copilot` | `GITHUB_TOKEN` | gpt-4o |
| `gemini` | `GEMINI_API_KEY` | gemini-1.5-pro |
| `opencode` | `OPENCODE_API_KEY` | — |
| `nous` | `NOUS_API_KEY` | hermes-3 |
| `sambanova` | `SAMBANOVA_API_KEY` | Meta-Llama-3.3-70B |
| `cline` | `CLINE_API_KEY` | — |
| `kilo` | `KILO_API_KEY` | — |
| `gateway` | `GATEWAY_API_KEY` | — |
| `minimax` | `MINIMAX_API_KEY` | minimax-text-01 |
| `ollama` | `OLLAMA_URL` | llama3.2 |
| `lmstudio` | `LMSTUDIO_URL` | — |
| `custom` | `SMART_APPLE_CUSTOM_*` | — |
| `none` | (no key) | — |

## Troubleshooting

### No `smartapple.toml` found
Run from a project directory, or `smart-apple-dev init <name>` first.

### SDK not installed
```bash
smart-apple-dev sdk list
smart-apple-dev sdk install --platform macosx --version 11.3
```
For iOS SDKs: extract on a Mac with `sdk extract`, then copy the archive.

### No devices found
Install `libimobiledevice` (`idevice_id -l` should list devices), trust the device.

### Fastlane not found
`pip install` doesn't include it — install Fastlane separately for `store/` helpers.

### Build fails: "no such sysroot"
Run `smart-apple-dev doctor` and `smart-apple-dev sdk list` to verify SDK path.

## What Isn't Yet CLI

- `store` — App Store Connect helpers exist as Python (`src/smartapple/store/`) but have no `smart-apple-dev store` command yet. Use the Python API or Fastlane directly.
- `--json` output — commands print human-readable output today.
- Structured logging — modules use `print()`; proper log levels are planned.

## See Also

- [README.md](README.md) — overview + verified status
- [ARCHITECTURE.md](ARCHITECTURE.md) — module map
- [PUBLISH_PLAN.md](PUBLISH_PLAN.md) — release ledger
- [PRICING.md](PRICING.md) — free vs paid
- [verify/verify.sh](verify/verify.sh) — end-to-end smoke test
- [verify/verify-android.sh](verify/verify-android.sh) — Android-specific smoke test
- [examples/hello-objc/](examples/hello-objc/) — Objective-C example
- [examples/hello-kotlin/](examples/hello-kotlin/) — Kotlin Multiplatform example
- [docs/](docs/) — MkDocs source for the documentation site
