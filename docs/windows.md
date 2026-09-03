# Windows

> **Use WSL2.** Native Windows PowerShell can't link Mach-O binaries; WSL
> gives you the same Linux environment as this repo's verified Linux host.

## Quickest path (elevated PowerShell)

```powershell
irm https://raw.githubusercontent.com/realstreetsmartnyc/smart-apple-dev/main/verify/setup-windows.ps1 | iex
```

This one-shot script:

1. Enables WSL2 and installs Ubuntu
2. Installs the Apple toolchain inside Ubuntu (`clang`, `lld`, `cmake`, …)
3. Clones the repo
4. Runs `verify.sh`

A full reboot may be required after step 1; the script will tell you.

## Manual path

### 1. Enable WSL2 and install Ubuntu

```powershell
wsl --install -d Ubuntu --no-launch
```

Reboot, then launch "Ubuntu" from the Start menu and finish first-boot
setup (Linux username + password).

### 2. Update Ubuntu and install the toolchain

Inside the Ubuntu window (NOT PowerShell):

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git curl make cmake \
                    clang lld llvm libplist-dev libssl-dev build-essential
```

### 3. Install smart-apple-dev

```bash
pipx install smart-apple-dev
# or: pip install --user smart-apple-dev
```

### 4. Run verify

```bash
git clone --depth=1 https://github.com/realstreetsmartnyc/smart-apple-dev
cd smart-apple-dev
./verify/verify.sh
```

## Where files live

| Resource | Path (inside WSL) |
|----------|-------------------|
| `smart-apple-dev` config | `~/.smart-apple-dev/` |
| Apple SDKs | `~/.smart-apple-dev/sdk/` |
| Cached tools (ldid, xtool) | `~/.smart-apple-dev/tools/` |

To access these from Windows Explorer: `\\wsl$\Ubuntu\home\<you>\.smart-apple-dev\`
