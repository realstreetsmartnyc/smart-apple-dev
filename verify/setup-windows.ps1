# smart-apple-dev Windows setup. Run this in an *elevated* PowerShell.
# What it does:
#   1. Enables WSL2 and installs Ubuntu
#   2. Installs the Apple toolchain inside Ubuntu
#   3. Clones smart-apple-dev
#   4. Runs verify.sh
# Requires: Windows 10 1809+ or Windows 11, admin rights.

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

Write-Host "==> Step 1/4: Enable WSL2 + Ubuntu" -ForegroundColor Cyan
wsl --install -d Ubuntu --no-launch
Write-Host "WSL2 enabled. Reboot if prompted, then re-run this script." -ForegroundColor Yellow

Write-Host "==> Step 2/4: Install Apple toolchain in Ubuntu" -ForegroundColor Cyan
wsl -d Ubuntu -- bash -lc @'
set -e
sudo apt update -qq && sudo apt upgrade -y -qq
sudo apt install -y -qq python3 python3-pip python3-venv git curl make cmake \
                       clang lld llvm libplist-dev libssl-dev build-essential
echo "Toolchain OK"
'@

Write-Host "==> Step 3/4: Clone smart-apple-dev" -ForegroundColor Cyan
wsl -d Ubuntu -- bash -lc "git clone --depth=1 https://github.com/realstreetsmartnyc/smart-apple-dev"

Write-Host "==> Step 4/4: Run verify.sh" -ForegroundColor Cyan
wsl -d Ubuntu -- bash -lc "cd smart-apple-dev && ./verify/verify.sh --local"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "Setup complete. To use smart-apple-dev daily:" -ForegroundColor Green
Write-Host "    wsl" -ForegroundColor White
Write-Host "    cd /mnt/c/Users/yourname/projects/yourcode" -ForegroundColor White
Write-Host "    smart-apple-dev init myapp --lang objc" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Green
