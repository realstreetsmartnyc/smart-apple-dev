# Verifying your install

`smart-apple-dev` ships a self-contained smoke test under [`verify/`][verify-dir] that
goes from a fresh machine to a built, signed `.ipa` and `.apk` artifact.

[verify-dir]: https://github.com/realstreetsmartnyc/smart-apple-dev/tree/main/verify

## `verify.sh` — full E2E on Linux / WSL2 / macOS

```bash
git clone https://github.com/realstreetsmartnyc/smart-apple-dev
cd smart-apple-dev
./verify/verify.sh              # full test
./verify/verify.sh --local      # use your local checkout (editable install)
./verify/verify.sh --skip-sdk   # don't fetch the Apple SDK
./verify/verify.sh --lang objc  # only test one language
```

What it does:

1. Detects your platform (Linux / WSL2 / macOS)
2. Installs missing system tools (`clang`, `lld`, `cmake`, …)
3. Builds `ldid` from source (no prebuilt Linux binary)
4. Downloads + extracts the macOS SDK if missing
5. Symlinks `ld64.lld` into `~/.smart-apple-dev/tools/`
6. Installs `smart-apple-dev` from PyPI (or local `./`)
7. For each language: `init → build → sign → ipa`
8. Prints a PASS/FAIL table; non-zero exit on any failure

## `verify-android.sh` — focused Android smoke test

```bash
./verify/verify-android.sh            # full test
./verify/verify-android.sh --local    # local checkout
./verify/verify-android.sh --skip-sdk # don't validate SDK contents
```

This is the test the CI `android` job runs internally. It:

1. Verifies JDK 17+ and `ANDROID_HOME`
2. Confirms `platforms;android-34` and `build-tools;34.0.0` are present
3. Builds `examples/hello-kotlin` end-to-end
4. Verifies the produced `.apk` contains `AndroidManifest.xml`
5. Stubs `adb` (with a fake shim) and runs `install --apk`

## CI

The same logic runs on every push to `main`:

- `.github/workflows/ci.yml` — Python tests + Android `assembleDebug` job
- The Android job installs JDK 17, Android cmdline-tools, and the platform
  34 SDK, then runs `assembleDebug` against `templates/kotlin/`.
