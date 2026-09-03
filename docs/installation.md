# Installation

## Via pip

```bash
pip install smart-apple-dev
```

## Via pipx (recommended for CLI use)

```bash
pipx install smart-apple-dev
```

This installs the CLI into an isolated venv and exposes `smart-apple-dev` on your `PATH`.

## From source

```bash
git clone https://github.com/realstreetsmartnyc/smart-apple-dev
cd smart-apple-dev
pip install -e ".[dev]"
```

## Requirements

| Requirement | Why |
|-------------|-----|
| Python 3.11+ | the CLI itself |
| `clang`, `lld` | C/C++/ObjC compilation and Mach-O linking on Linux |
| `git`, `curl`, `make`, `tar` | SDK + ldid fetching |
| Apple SDK | `smart-apple-dev sdk install` fetches it for you |

### Optional (per workflow)

| Workflow | Needs |
|----------|-------|
| iOS / macOS device install | `libimobiledevice` (`apt install libimobiledevice`) |
| Android build | JDK 17+ + Android SDK with `platforms;android-34` + `build-tools;34.0.0` |
| Android device install | `adb` (`apt install adb`) |
| Swift | `xtool` (auto-installed by `doctor --install`) |
| App Store upload | `fastlane` or `altoo` |
