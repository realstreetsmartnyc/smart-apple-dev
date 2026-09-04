# Linux / WSL

Most users — including the project maintainer — develop on Linux or inside
WSL2. This page collects the platform-specific gotchas.

## Distribution support

Tested on:

- Ubuntu 22.04 LTS
- Ubuntu 24.04 LTS
- Debian 12 (Bookworm)
- WSL2 Ubuntu (any LTS)

## Native dependencies

```bash
sudo apt update
sudo apt install -y clang lld cmake make git curl tar \
                    libplist-dev libssl-dev build-essential

# Optional, per workflow
sudo apt install -y libimobiledevice-utils  # iOS device install
sudo apt install -y adb                     # Android device install
sudo apt install -y openjdk-17-jdk          # Android builds
```

## Swift for Linux (xtool)

`smart-apple-dev` supports Swift development on Linux through `xtool`,
a cross-platform Xcode replacement written in Swift.

### Installing xtool

```bash
# Downloads Swift for Linux (~600 MB) and builds xtool from source
smart-apple-dev xtool install
```

This installs:
- `~/.smart-apple-dev/swift/` — Swift toolchain
- `~/.smart-apple-dev/xtool/` — xtool source + build artifacts
- `~/.smart-apple-dev/tools/` — symlinks for `swift`, `xtool`, `ldid`, `ld64.lld`

### Status

```bash
smart-apple-dev xtool status
```

Reports whether Swift, xtool, and the tools are on PATH.

### Prerequisites on Linux

- `git`, `curl`, or `aria2c` (aria2c is faster for the 600 MB download)
- At least 5 GB free disk space (falls back to `/tmp/sad-install/` if home is tight)

### Swift on macOS

On macOS, Swift is pre-installed. No extra steps needed.

## Apple SDK

The Apple SDKs are proprietary. On a Mac, run `smart-apple-dev sdk extract`
to package the SDK into a tarball, then transfer it to your Linux box and
`smart-apple-dev sdk install --platform macosx` (or `iphoneos`).

If you don't have a Mac, community builds are available; the `verify.sh`
script downloads a known-good `MacOSX11.3.sdk.tar.xz` automatically.

## ldid

The only signing tool with a prebuilt Mac binary is `ldid`. The Linux
binary doesn't exist upstream, so `verify.sh` builds it from source. You
can also build it yourself:

```bash
git clone https://github.com/saurik/ldid.git
cd ldid && g++ -I . -o ldid ldid.cpp util.cpp -lcrypto -lpthread
cp ldid ~/.smart-apple-dev/tools/
```

## WSL2

Inside WSL2, the environment is identical to native Linux. The
`verify/setup-windows.ps1` script does the WSL2 + Ubuntu + toolchain +
`verify.sh` dance in one shot from elevated PowerShell.

## Common issues

### "Mach-O link error: unknown architecture"

You have Apple's `cctools` but not `lld`. Install `lld` and try again:

```bash
sudo apt install lld
which ld64.lld      # should print /usr/bin/ld64.lld
```

### "No Android device found"

```bash
adb devices          # empty? check USB cable + USB debugging on the device
adb start-server     # in case the daemon got into a bad state
```

### "permission denied" running gradlew

```bash
chmod +x ./gradlew
```
