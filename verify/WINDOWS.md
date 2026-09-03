# smart-apple-dev on Windows — Windows form via WSL2

> This is the only supported way to develop macOS/iOS apps and games from
> Windows using smart-apple-dev. Run everything from inside WSL2 (Ubuntu).
> Native Windows PowerShell can't link Mach-O binaries; WSL gives you
> the same Linux environment as this repo's verified Linux host.

## One-time setup on a Windows machine

Open **PowerShell as Administrator** (right-click → "Run as administrator")
and paste these commands. Each one is idempotent — safe to re-run.

### 1. Enable WSL2 and install Ubuntu

```powershell
# Enable the WSL feature and install Ubuntu (default distro)
wsl --install -d Ubuntu --no-launch

# Restart is automatic after the first run; if not, reboot manually
# Then launch "Ubuntu" from the Start menu to finish first-boot setup
# (it will ask you to create a Linux username + password)
```

### 2. Update Ubuntu and install the Linux toolchain

Paste this inside the Ubuntu window (NOT in PowerShell):

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git curl make cmake                     clang lld llvm libplist-dev libssl-dev build-essential

# Verify
clang --version
ld.lld --version    # LLVM's Mach-O linker is ld64.lld, exposed here as ld.lld
```

### 3. Get the smart-apple-dev repo and run verify.sh

```bash
git clone --depth=1 https://github.com/realstreetsmartnyc/smart-apple-dev
cd smart-apple-dev
./verify/verify.sh --local
```

You should see something like:

```
=== Per-language smoke test ===
[PASS]  objc  ipa 4789 bytes
[PASS]  cpp   ipa 36861 bytes
[PASS]  rust  ipa 191699 bytes
[PASS]  go    ipa 1357243 bytes
[WARN]  kotlin kotlinc not installed; skipping
[WARN]  swift swift not installed (xtool also absent); skipping

=== Summary ===
  PASS=9  FAIL=0  WARN=2
ALL CHECKS PASSED
```

If you see `ALL CHECKS PASSED`, the toolchain is working end-to-end on your
Windows machine (via WSL2). Every PASS line is a real `.app` bundle signed by
ldid and packaged into a real `.ipa`.

### 4. Daily workflow

After setup, every time you want to develop:

```powershell
# In Windows: open the WSL shell
wsl
```

```bash
# Inside WSL: navigate to your project (Windows files live under /mnt/c/...)
cd /mnt/c/Users/yourname/projects/yourcode

# Use smart-apple-dev exactly as on Linux
smart-apple-dev init myapp --lang objc
cd myapp
smart-apple-dev build --target macos
smart-apple-dev sign --mode ad-hoc --ipa --target macos
```

## What works in WSL2

| Capability | Status | Evidence |
|---|---|---|
| `smart-apple-dev init` for objc, cpp, rust, go | ✅ | verified on Linux, identical env in WSL2 |
| `smart-apple-dev build --target macos` | ✅ | produces real Mach-O in `.app` |
| `smart-apple-dev sign --mode ad-hoc --ipa` | ✅ | produces real `.ipa` |
| iOS device install (libimobiledevice + USB) | ⚠️ | USB passthrough needs `usbipd-win` on Windows host |
| App Store / notarization | ⚠️ | still requires a real Mac for `xcrun notarytool` |

## iOS device testing from Windows

USB devices don't pass through WSL2 by default. To install an IPA on a
physical iPhone from WSL2, install **usbipd-win** on the Windows side:

```powershell
# In elevated PowerShell on Windows
winget install usbipd
# Then for each iPhone you plug in:
usbipd list
# Find the iPhone's BUSID, e.g. 4-2
usbipd bind --busid 4-2
usbipd attach --wsl --busid 4-2
```

Then inside WSL:

```bash
sudo apt install -y libimobiledevice-utils usbmuxd
idevice_id 4-2 -l
ideviceinstaller 4-2 -i build/macos/yourapp.ipa
```

## Why not native Windows PowerShell?

| What | WSL2 Ubuntu | Native Windows |
|---|---|---|
| `clang` cross-compile | works | works (LLVM ships native) |
| `ld64.lld` (Mach-O linker) | works | works |
| Apple SDK headers | works | works |
| `codesign` / `notarytool` | needs SSH to a Mac | needs SSH to a Mac |
| `libimobiledevice` for iPhone install | works with usbipd | broken (no usbmuxd) |
| App Store upload | needs Mac | needs Mac |

Bottom line: **WSL2 is the supported path.** Native Windows works for
compiling, but breaks the moment you try to install on a real iPhone.

## What still requires a Mac (any approach)

- iOS App Store submission (`xcrun altool` / Transporter)
- macOS notarization for distribution outside the App Store
- Apple Push Notification service key generation
- TestFlight uploads

The workaround is to keep a cheap remote macOS worker
(BuildJet / MacStadium / GitHub Actions `macos-latest`) and run those
steps from CI rather than from your dev machine.

## Troubleshooting

### "verify.sh: clang not found"
```bash
sudo apt install -y clang lld
```

### "verify.sh: No smartapple.toml found"
The CLI looks for `smartapple.toml` by walking up from the current directory.
Always `cd` into the project root (the one containing `smartapple.toml`)
before running `build` or `sign`.

### "tar: Cannot create symlink: No space left on device"
The macOS SDK is ~600 MB extracted (lots of symlinks). Make sure
`%LocalAppData%\Packages\CanonicalGroupLimited.Ubuntu...\` has at
least 2 GB free, or move WSL2 to another drive:
```powershell
wsl --export Ubuntu ubuntu.tar
wsl --unregister Ubuntu
wsl --import Ubuntu D:\WSL ubuntu.tar
```

### "permission denied" on USB devices in WSL
You need the Windows-side `usbipd` step described in the iOS section above.
