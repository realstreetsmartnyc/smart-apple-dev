# FAQ

### Do I need a Mac to build iOS apps?

No. `smart-apple-dev` runs end-to-end on Linux using `clang` + `ld64.lld`
+ the Apple SDK. You do need an Apple Developer ID for App Store
distribution (see [iOS / macOS](ios-macos.md)).

### Can I build for both iOS and Android from one codebase?

Yes — the Kotlin template is a Kotlin Multiplatform project with
`commonMain` for shared code and per-platform source sets for
iOS-specific and Android-specific code. See [Android](android.md).

### Does it work on Windows?

Use WSL2. The `verify/setup-windows.ps1` script does the whole
WSL2 + Ubuntu + toolchain + smoke-test dance. See [Windows](windows.md).

### Why another iOS build tool? What's different from `fastlane`?

`fastlane` orchestrates Xcode and assumes you have a Mac. `smart-apple-dev`
shells out to `clang` + `ld64.lld` directly and runs on Linux. It also
unifies Apple, Android, and an LLM agent in a single CLI.

### Is it free?

Yes. MIT-licensed. Optional paid add-ons (Cloud Build, LLM Gateway) are
listed in [Pricing](pricing.md) but the core CLI is free forever.

### Where are my projects stored?

`~/.smart-apple-dev/` holds the SDK, tools (`ldid`, `xtool`), and per-user
config. Each project is just a directory with a `smartapple.toml`.

### How do I add a new language or provider?

See [`ARCHITECTURE.md`](https://github.com/realstreetsmartnyc/smart-apple-dev/blob/main/ARCHITECTURE.md) — each language is a Python
class in `src/smartapple/build/<lang>.py`, each provider is a subclass
of `BuildProvider` in `src/smartapple/build/provider.py`.

### Why are some languages marked 🟡 in the README?

"Experimental" means: the backend exists and runs for simple projects,
but edge cases (custom linker flags, KMP shared code, etc.) are still
being polished. Each 🟡 backend has open issues tagged with the
language name.

### Where do I report bugs?

Open an issue at
[github.com/realstreetsmartnyc/smart-apple-dev/issues][issues].
For security issues, see [`SECURITY.md`](https://github.com/realstreetsmartnyc/smart-apple-dev/blob/main/SECURITY.md).

[issues]: https://github.com/realstreetsmartnyc/smart-apple-dev/issues
