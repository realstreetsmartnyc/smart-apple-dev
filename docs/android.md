# Android

<p align="center">
  <img src="banner-android.svg" width="640" alt="smart-apple-dev Android banner">
</p>

The Kotlin template is a **Kotlin Multiplatform** project that builds
**both** an Android APK and an iOS binary from a single `commonMain` source
set. No Xcode, no Mac — just JDK 17+ and the Android SDK.

## 1. One-time setup

```bash
# Install the JDK
sudo apt install openjdk-17-jdk          # or: brew install openjdk@17

# Set ANDROID_HOME (where you installed Android Studio's SDK, or sdkmanager)
export ANDROID_HOME=$HOME/Android/Sdk
export PATH=$ANDROID_HOME/platform-tools:$ANDROID_HOME/cmdline-tools/latest/bin:$PATH

# Install the SDK platform + build tools
yes | sdkmanager --licenses
sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0"
```

## 2. Scaffold + build

```bash
smart-apple-dev init hello --lang kotlin
cd hello
smart-apple-dev build --target android
# → build/outputs/apk/debug/hello-debug.apk
```

Or run Gradle directly:

```bash
./gradlew assembleDebug                # debug APK
./gradlew assembleRelease              # release APK
```

## 3. Install on a device

With a device connected over USB (USB debugging enabled) or an emulator running:

```bash
smart-apple-dev devices --platform android
smart-apple-dev install --apk build/outputs/apk/debug/hello-debug.apk
```

## What's in the template

```
hello/
├── build.gradle.kts           # KMP: androidTarget {} + iosArm64 {}, Firebase BoM
├── settings.gradle.kts        # Kotlin 1.9.20, AGP 8.2.2, Google Services 4.5.0
├── google-services.json
├── src/
│   ├── commonMain/
│   │   └── kotlin/
│   │       └── Main.kt        # Shared: `fun main() { ... }`
│   ├── androidMain/
│   │   └── kotlin/app/
│   │       └── MainActivity.kt # Android Activity
│   └── main/
│       └── AndroidManifest.xml # LAUNCHER intent
└── smartapple.toml
```

## How it works

`smart-apple-dev build --target android` shells out to `./gradlew assembleDebug`
(or `assembleRelease` with `--release`), then locates the produced APK in
`build/outputs/apk/<flavor>/`. The CLI captures and surfaces common Android
build failures with actionable hints:

- `ANDROID_HOME` not set → `Set ANDROID_HOME or ANDROID_SDK_ROOT`
- JDK < 17 → `Install JDK 17+`
- Android licenses unaccepted → `yes | sdkmanager --licenses`
- `gradlew` not executable → `chmod +x gradlew`

## Verifying

A focused smoke test lives in [`verify/verify-android.sh`][verify-android].
It builds `examples/hello-kotlin` end-to-end and verifies the APK is a
valid ZIP with `AndroidManifest.xml` inside. The same logic runs on every
push via the CI `android` job.

[verify-android]: https://github.com/realstreetsmartnyc/smart-apple-dev/blob/main/verify/verify-android.sh

## Example project

A full rendered example lives at
[`examples/hello-kotlin/`](https://github.com/realstreetsmartnyc/smart-apple-dev/tree/main/examples/hello-kotlin).
