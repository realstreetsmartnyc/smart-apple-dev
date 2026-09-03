# Quickstart

## 1. Verify your install

```bash
smart-apple-dev doctor
```

If anything is missing, run `smart-apple-dev doctor --install` and re-check.

## 2. Scaffold your first project

```bash
smart-apple-dev init hello --lang objc
cd hello
```

This creates:

- `smartapple.toml` — the project config
- `main.m` + `Info.plist` — the app sources
- A `.app` target via `clang` + `ld64.lld` + the Apple SDK

## 3. Build

```bash
smart-apple-dev build --target macos
```

## 4. Sign and package

```bash
smart-apple-dev sign --mode ad-hoc --ipa
```

Output: `build/macos/hello.ipa`.

## 5. Install to a device

```bash
smart-apple-dev devices
smart-apple-dev install --ipa build/macos/hello.ipa
```

For Android, see the [Android guide](android.md).

## Verified Status

Every row below is tied to passing tests or manual verification on Linux
(Ubuntu 22.04, Python 3.11–3.13). Nothing is claimed without evidence.

| Capability | Status | Evidence |
|------------|--------|----------|
| CLI entry point | ✅ | `pytest` |
| `smartapple.toml` config | ✅ | `test_config.py` |
| Build orchestrator | ✅ | `test_orchestrator.py` |
| C/C++ Mach-O builds | ✅ | `test_build_cpp.py` |
| ObjC builds (clang+SDK) | ✅ | `test_provider.py` |
| Swift (via xtool) | ✅ code, ⚠️ needs xtool | manual |
| Rust / Go / Kotlin | ✅ code, ⚠️ needs toolchain | manual |
| Android (Kotlin) target | ✅ | `test_android_target.py`, CI `android` job |
| Signing + IPA packaging | ✅ | `test_sign.py` |
| `ldid` auto-fetch | ✅ | `doctor.py` |
| Device install (iOS) | ✅ code, ⚠️ needs libimobiledevice | manual |
| Device install (Android, adb) | ✅ code, ⚠️ needs adb | `test_android_target.py` |
| 12 build providers | ✅ | `test_provider.py` |
| 21 LLM providers | ✅ | `test_agent.py` |
