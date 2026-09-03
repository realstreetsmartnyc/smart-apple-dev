# hello-kotlin — Android (Kotlin Multiplatform) Example

A minimal Kotlin Multiplatform app that builds **both** an Android APK
**and** an iOS binary from a single `commonMain` source set.

Generated with:

```bash
smart-apple-dev init hello-kotlin --lang kotlin
cd hello-kotlin
smart-apple-dev build --target android
# -> build/outputs/apk/debug/hello-kotlin-debug.apk
```

## What's in here

| File | What it is |
|------|------------|
| `build.gradle.kts` | Kotlin Multiplatform build: `androidTarget {}` + `iosArm64 {}` + Firebase BoM 34.18.0 |
| `settings.gradle.kts` | Plugin management (Kotlin 1.9.20, AGP 8.2.2, Google Services 4.5.0) |
| `src/commonMain/kotlin/Main.kt` | Top-level `fun main()` — shared between Android and iOS |
| `src/androidMain/kotlin/app/MainActivity.kt` | Android Activity that displays the greeting |
| `src/main/AndroidManifest.xml` | Standard Android manifest with LAUNCHER intent |
| `smartapple.toml` | Project config (created by `init`) |
| `google-services.json` | Firebase config — replace with your own |

## Building

### Android (APK)

```bash
# one-time
export ANDROID_HOME=$HOME/Android/Sdk
yes | sdkmanager --licenses
sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0"

# build
smart-apple-dev build --target android
# or, raw:
cd hello-kotlin && ./gradlew assembleDebug
```

Output: `build/outputs/apk/debug/hello-kotlin-debug.apk`

### iOS device binary (Kotlin/Native)

```bash
smart-apple-dev build --target ios
# or, raw:
cd hello-kotlin && ./gradlew linkDebugExecutableIosArm64
```

Output: `build/binaries/debug/iosArm64/hello-kotlin.kexe`

## Install on a device

```bash
# Android (USB debugging on, device visible to `adb devices`)
smart-apple-dev install --apk build/outputs/apk/debug/hello-kotlin-debug.apk
```

## Regenerate from scratch

```bash
rm -rf hello-kotlin
smart-apple-dev init hello-kotlin --lang kotlin
```

## See also

- `examples/hello-objc/` — Objective-C macOS example
- `docs/banner-android.svg` — branding for the Android feature
- `verify/verify-android.sh` — automated smoke test for the Android path
