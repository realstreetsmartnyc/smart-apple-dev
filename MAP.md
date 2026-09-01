"""smart-apple-dev — Wayfinding Map

## Destination

A cross-platform (Linux/Windows) iOS/macOS development toolchain that runs natively
on Linux and Windows, unifying build, sign, install, and deploy iOS/macOS apps
without needing a Mac.

## Decisions (D1-D8 — all resolved)

- [D1 — Name] **Decided.** smart-apple-dev (confirmed by user).
- [D2 — Platform scope] **Decided.** Linux + Windows native, macOS bonus.
- [D3 — Language scope] **Decided.** Swift, Objective-C, C, C++, Rust, Go, Kotlin/Native — all iOS/macOS-capable.
- [D4 — Pipeline scope] **Decided.** Build → Sign → Install → Device Test → App Store Connect.
- [D5 — Open-source] **Decided.** Yes, MIT license. Self-hostable. No cloud Mac required.
- [D6 — Code organization] **Decided.** Modules consolidated in single `__init__.py` files (sign/`, `device/`, `store/`) for MVP simplicity. Split into submodules later if needed.
- [D7 — SDK extraction strategy] **Decided.** Extract once on Mac with `sdk extract`, cache in `~/.smart-apple-dev/sdk/`, reuse on Linux/Windows. Same approach as osxcross.
- [D8 — Signing architecture] **Decided.** cctools-port + ldid on Linux. Apple cert chain required for identity signing. Ad-hoc signing supported out of the box.
- [D9 — Device testing on Linux] **Decided.** libimobileddevice + usbmuxd.
- [D10 — App Store Connect API] **Decided.** Fastlane primary, altool fallback. API-key-based auth documented.
- [D11 — IDE/editor integration] **Deferred to v1.1.** VS Code plugin is stretch goal.
- [D12 — Build system abstraction] **Decided.** BuildOrchestrator + per-language backends (swift, objc/cpp, rust, go, kotlin). Providers handle *where* the build runs (local vs. SSH-to-Mac vs. cloud).
- [D13 — Distribution model] **Decided.** Single package on PyPI. Language toolchains are system deps (clang, cargo, go, kotlin, xtool).
- [D14 — Agent scope] **Decided.** LLM agent loop with toolbelt (10 tools). Supports Anthropic, OpenAI, Ollama, or deterministic plan mode (no LLM). Per-project memory persisted as JSON.
- [D15 — Cloud provider scope] **Deferred to v1.2.** SSH provider implemented in v1.0 as a proof-of-concept. GitHub Actions and AWS Mac are future options.

## Not yet specified / open for v2.0

- SwiftUI Preview alternative (out of scope)
- iOS Simulator (out of scope — requires macOS + Metal)
- Full Xcode GUI replacement (out of scope)
- Cloud Mac hosting (we're building the local alternative)
- Kotlin/Native backend CI testing (requires Kotlin SDK in CI)
