## [1.0.2] - 2026-09-04
### Fixed
- **ObjC backend**: prioritize clang/osxcross over xtool shim; the Python
  xtool shim only handles Swift commands and caused ObjC builds to fail
- **CI**: PyPI publish job now uses `continue-on-error: true` so a missing or
  invalid `PYPI_API_TOKEN` doesn't block CI
- **CI**: JDK 17 auto-detected in verify job for Android Kotlin builds

### Added
- **Tests**: `tests/test_xtool_env.py` — 11 tests for xtool environment manager
  (XtoolStatus, install_root, status snapshots)
- **Tests**: `tests/test_notarize.py` — 14 tests for notarization module
  (NotarizeResult, zip creation, macOS/local/remote paths)
- **Tests**: `tests/test_template_gitignore.py` — 3 tests ensuring every
  language template ships a .gitignore
- **Templates**: `.gitignore` added to all 7 language templates (swift,
  kotlin, godot, cpp, go, rust, objc)

### Changed
- **ObjC backend**: documented that xtool is a last-resort fallback for ObjC;
  clang/osxcross is preferred

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2026-09-03

### Added
- **`smart-apple-dev notarize`**: macOS notarization helper. On macOS uses
  `xcrun notarytool` + `xcrun stapler`; on Linux/Windows requires `--remote
  user@host` to SSH into a Mac and notarize there
- **`smart-apple-dev xtool` subcommand group** (`status`, `install`, `uninstall`,
  `verify`): manage xtool Swift environment on Linux/Windows (Swift toolchain
  download + xtool build from source, ~600 MB + ~5 min)
- **`doctor --install`** now auto-installs `clang/lld/cmake` and
  `libimobiledevice` via `apt-get` on Debian/Ubuntu, and Godot export
  templates (~1 GB download) for the Godot game path
- **`doctor --json`**: machine-readable JSON output for agent tooling
- **`smart-apple-dev new`**: alias for `init` that scaffolds a project
  and prints next steps (build, sign, install, notarize)
- **`templates/godot/`**: real Godot 4 project template (project.godot,
  Main.tscn, Main.gd, export_presets.cfg) — replaces the old toml-only stub
- **`examples/hello-swiftui/`**: full SwiftUI app example with Combine,
  CoreData, CoreLocation, and notifications

### Changed
- **Rust backend** auto-adds Apple targets on first build: runs
  `rustup target add --toolchain stable <triple>` instead of failing
- **CI workflow** adds a `verify` job that runs `./verify/verify.sh --local`
  on every PR, and an `android` job that builds the Kotlin template APK
  via Gradle + verifies `AndroidManifest.xml`. `publish` now requires
  both `test` and `verify` to pass
- **`chore(templates)`**: deleted empty `templates/swiftui/` and
  `templates/unity/` stubs that produced broken projects

### Fixed
- `verify.sh` SCRIPT_DIR fallback for the kotlin/Android path so it
  resolves correctly when sourced
- `.gitignore` excludes `templates/*/.godot/` editor cache

[1.0.1]: https://github.com/realstreetsmartnyc/smart-apple-dev/releases/tag/v1.0.1

## [1.0.0] - 2026-09-03

### Added
- Cross-platform CLI (`smart-apple-dev`) with 11 commands: `init`, `build`, `sign`, `install`, `devices`, `doctor`, `info`, `provider`, `sdk`, `check`, `agent`
- 7 language templates: Swift, Objective-C, C++, Rust, Go, Kotlin (+ 5 experimental: Java, JavaScript, Python, C#, game engines)
- 12 build providers: local (clang+ld64.lld+SDK), SSH, GitHub Actions, AWS Mac, Azure, Codemagic, Bitrise, BuildJet, Jenkins, CircleCI, MacStadium, Nevercode
- 21 LLM providers: none, anthropic, openai, ollama, lmstudio, custom, groq, mistral, together, xai, deepseek, perplexity, copilot, gemini, opencode, nous, sambanova, cline, kilo, gateway, minimax
- Named LLM instances via `base:label` syntax (e.g. `copilot:default`, `custom:venice`) with persistent config at `~/.smart-apple-dev/llm-providers.json`
- Agentic loop with 10 tools (doctor, build, sign, install, sdk_list, read_file, write_file, run_shell, provider_list, ask_user)
- Mach-O signing via `ldid` with IPA packaging and verification
- SDK management: download, extract, and index Apple SDKs
- Firebase integration templates
- GitHub Actions CI (Python 3.11/3.12/3.13, ruff, mypy, pytest, coverage)
- PyPI publish workflow on version tags
- **`android` build target** for the Kotlin template (assembles debug/release APK via `./gradlew assembleDebug` / `assembleRelease`; auto-locates the APK under `build/outputs/apk/`)
- **Android device install** via `adb` (`list_android_devices`, `install_apk`); `devices --platform android|all` enumerates phones and emulators
- **`install` command** now accepts `--apk <path>` and `--platform ios|android|auto`
- **Android CI job** in `.github/workflows/ci.yml` — installs JDK 17 + Android cmdline-tools, builds the Kotlin template's debug APK on Ubuntu, and verifies the artifact contains `AndroidManifest.xml`
- **`.app` bundle creation** in Go and Rust backends on `darwin` targets — wrap the raw Mach-O binary in `Contents/MacOS/<name>` with an `Info.plist` so the existing sign / pack_ipa pipeline works
- **Linux → Apple cross-compile** for Rust: point cargo's linker at `clang` + `ld64.lld` for `*-apple-darwin` and `*-apple-ios` targets via `CARGO_TARGET_<TRIPLE>_LINKER` + `RUSTFLAGS`
- **Kotlin Multiplatform** template now correctly declares `androidTarget {}` + `iosArm64 {}`, with `commonMain` / `androidMain` source sets, a `MainActivity` for Android, and a real `AndroidManifest.xml`
- **Android example** at `examples/hello-kotlin/` — fully rendered, no placeholders, with its own README
- **End-to-end smoke test** at `verify/verify.sh` (Linux / WSL2 / macOS) and the focused `verify/verify-android.sh` (Android)
- **Windows admin bootstrapper** at `verify/setup-windows.ps1` + `verify/WINDOWS.md` (WSL2 + Ubuntu + toolchain + verify.sh in one shot)
- **MkDocs site** (Material theme) with `mkdocs.yml` + 18 docs/ pages; auto-deployed to GitHub Pages via `.github/workflows/docs.yml`
- **`docs/banner-android.svg`** (1280×640) social preview for the Android feature
- **Rich-based UI** (`src/smartapple/ui.py`) with banner / step / success / warning / error / hint / spinner / summary / panel — colored on TTY, ASCII on CI, with `SMART_APPLE_DEV_NO_COLOR` and `SMART_APPLE_DEV_FORCE_COLOR` env knobs
- **Release workflow** (`.github/workflows/release.yml`) — auto-creates a GitHub Release on `v*` tag, attaches wheel/sdist + examples, extracts notes from `CHANGELOG.md`
- 147 tests pass on Linux (was 108); Android path covered by 20 tests in `test_android_target.py`, UI by 18 in `test_ui.py`, templates by 16 in `test_templates.py`

### Fixed
- Template rendering: `module {{NAME}}` in Go, recursive `{{BUNDLE_ID}}` substitution
- ld64.lld discovery and Mach-O verification
- `gradlew` executable bit on Linux (template is now `chmod +x`-ready)
- All `templates/*/smartapple.toml` files now use the standard `[project]` TOML structure that `init` writes (previously they were a confusing mix of Jinja and TOML)

[1.0.0]: https://github.com/realstreetsmartnyc/smart-apple-dev/releases/tag/v1.0.0
