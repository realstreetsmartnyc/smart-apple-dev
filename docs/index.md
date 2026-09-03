# smart-apple-dev

**Cross-platform iOS / macOS / Android development CLI — no Mac required.**

<p align="center">
  <img src="banner.svg" width="640" alt="smart-apple-dev banner">
</p>

!!! tip "v1.0.0 — public beta"
    Core pipeline verified on Linux. See [Verified Status](quickstart.md#verified-status)
    for what works today, and [Android](android.md) for the new APK build path.

## Why smart-apple-dev?

- **No Mac tax** — build iOS / macOS apps on Linux or Windows with `clang` + `ld64.lld` + Apple SDKs
- **Android too** — the Kotlin template is a Kotlin Multiplatform project that also produces an APK
- **Any language** — Swift, Objective-C, C/C++, Rust, Go, Kotlin (and more)
- **Any Mac** — local, SSH, or 12 cloud CI providers (GitHub Actions, AWS Mac, BuildJet, MacStadium…)
- **Agent-powered** — 21 LLM providers, `base:label` named instances, tool-using loop
- **Open and self-hostable** — MIT, no vendor lock-in, BYOK

## 60-second demo

```bash
pip install smart-apple-dev
smart-apple-dev doctor
smart-apple-dev info

# Scaffold and build
smart-apple-dev init hello --lang objc
cd hello
smart-apple-dev build --target macos
smart-apple-dev sign --ipa
# → build/macos/hello.ipa
```

## What the output looks like

```
$ smart-apple-dev build --target android
[INFO] Building hello for android via local
[OK] Build succeeded via local (kotlin)
     Build    succeeded
  Provider    local
  Language    kotlin
    Target    android
  Artifact    build/outputs/apk/debug/hello-debug.apk
  Duration    12.3s
```

## Get started

<div class="grid cards" markdown>

- :material-download: &nbsp; **[Installation](installation.md)**

    Install via `pip`, `pipx`, or from source.

- :material-rocket-launch: &nbsp; **[Quickstart](quickstart.md)**

    Scaffold, build, sign, and ship your first iOS or Android app.

- :material-android: &nbsp; **[Android](android.md)**

    Build an APK from the same CLI; no Xcode required.

- :material-shield-check: &nbsp; **[Verifying](verifying.md)**

    Run `verify/verify.sh` for an end-to-end smoke test on a fresh machine.

</div>

## Verified

- ✅ 138+ tests passing on Linux
- ✅ 12 build providers, 21 LLM providers
- ✅ Android APK build via Gradle (CI-verified)
- ✅ 7 language templates, 5 more experimental

See the [Verified Status](quickstart.md#verified-status) table for evidence per claim.
