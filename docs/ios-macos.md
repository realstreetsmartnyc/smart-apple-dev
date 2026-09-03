# iOS / macOS

> See the [Quickstart](quickstart.md) for the full hello-world walkthrough.
> This page focuses on what the Apple pipeline does under the hood and the
> commands that are specific to Apple targets.

## Build targets

| `--target` | Compiler | Notes |
|------------|----------|-------|
| `macos`    | clang + ld64.lld | Native Mach-O; produces a `.app` bundle on macOS, a raw Mach-O on Linux |
| `ios`      | clang + ld64.lld | iOS device; requires Apple iPhoneOS SDK |
| `ios-simulator` | clang + ld64.lld | iOS simulator; macOS-only (Apple's sim runtime isn't redistributable) |
| `catalyst` | clang + ld64.lld | Mac Catalyst; requires macOS SDK ≥ 10.15 |

```bash
smart-apple-dev build --target macos
smart-apple-dev build --target ios
```

## Signing

Three modes:

- `ad-hoc` (default) — `ldid` with no identity; works on Linux, no cert needed
- `identity` — use your Apple Developer ID + `.mobileprovision` (macOS only)
- `skip` — build only, no signing

```bash
# Linux, ad-hoc
smart-apple-dev sign --mode ad-hoc --ipa

# macOS, real cert
smart-apple-dev sign --mode identity --identity "Apple Development: ..." --profile ./profile.mobileprovision
```

## Device install (Linux)

```bash
sudo apt install libimobiledevice
smart-apple-dev devices
smart-apple-dev install --ipa build/ios/hello.ipa
```

## 12 build providers

See [Build providers](providers.md) for the full list — local, SSH, GitHub
Actions, AWS Mac, Azure, CircleCI, MacStadium, Codemagic, Bitrise, BuildJet,
Jenkins, Nevercode.
