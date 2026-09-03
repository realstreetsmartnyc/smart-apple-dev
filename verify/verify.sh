#!/usr/bin/env bash
# verify.sh — End-to-end smoke test for smart-apple-dev on Linux / WSL2 / macOS.
#
# What it does:
#   1. Detects platform (Linux, macOS, WSL2)
#   2. Installs missing system tools (clang, lld, cmake, etc.)
#   3. Builds ldid from source (no prebuilt Linux binary exists)
#   4. Extracts the macOS SDK (if a tarball is present, else downloads one)
#   5. Symlinks ld64.lld into ~/.smart-apple-dev/tools/
#   6. Installs smart-apple-dev (from PyPI or local ./smart-apple-dev)
#   7. For each supported language: init -> build -> sign -> ipa
#   8. Prints a PASS/FAIL table and exits non-zero on any failure
#
# Usage:
#   ./verify.sh                  # full test
#   ./verify.sh --local          # test local ./smart-apple-dev checkout (editable)
#   ./verify.sh --skip-sdk       # don't try to download/extract SDK
#   ./verify.sh --lang objc,cpp  # only test specific languages

set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---------- Configuration ----------
SAD_HOME="${SAD_HOME:-$HOME/.smart-apple-dev}"
TOOLS_DIR="$SAD_HOME/tools"
SDK_DIR="$SAD_HOME/sdk"
SDK_TARBALL_URL_DEFAULT="https://github.com/phracker/MacOSX-SDKs/releases/download/11.3/MacOSX11.3.sdk.tar.xz"
LDID_REPO="https://github.com/opa334/ldid.git"
LDID_BUILD_DEPS_LINUX=(git make g++ libplist-dev libssl-dev)
PYTHON_BIN="${PYTHON_BIN:-python3}"
USE_LOCAL=0
SKIP_SDK=0
LANGS_FILTER=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --local) USE_LOCAL=1; shift ;;
        --skip-sdk) SKIP_SDK=1; shift ;;
        --lang) LANGS_FILTER="$2"; shift 2 ;;
        --sdk-url) SDK_TARBALL_URL_DEFAULT="$2"; shift 2 ;;
        -h|--help)
            head -22 "$0" | tail -20
            exit 0 ;;
        *) echo "Unknown arg: $1" >&2; exit 2 ;;
    esac
done

ALL_LANGS=(objc cpp rust go kotlin swift)
if [[ -n "$LANGS_FILTER" ]]; then
    IFS=',' read -ra LANGS <<< "$LANGS_FILTER"
else
    LANGS=("${ALL_LANGS[@]}")
fi

# ---------- Pretty output ----------
if [[ -t 1 ]]; then
    C_OK=$'\033[32m'; C_FAIL=$'\033[31m'; C_WARN=$'\033[33m'; C_INFO=$'\033[36m'; C_RST=$'\033[0m'
else
    C_OK=''; C_FAIL=''; C_WARN=''; C_INFO=''; C_RST=''
fi

PASS=0
FAIL=0
WARN=0
declare -A RESULTS  #  # RESULTS[step]=PASS|FAIL|WARN|msg

step() { echo; echo "${C_INFO}=== $* ===${C_RST}"; }
pass() { PASS=$((PASS+1)); echo "${C_OK}[PASS]${C_RST}  $*"; RESULTS["$1"]="PASS"; }
fail() { FAIL=$((FAIL+1)); echo "${C_FAIL}[FAIL]${C_RST}  $*"; RESULTS["$1"]="FAIL|$2"; }
warn() { WARN=$((WARN+1)); echo "${C_WARN}[WARN]${C_RST}  $*"; RESULTS["$1"]="WARN|$2"; }
info() { echo "       $*"; }

detect_platform() {
    step "Platform detection"
    if [[ -f /proc/version ]] && grep -qi microsoft /proc/version 2>/dev/null; then
        PLATFORM="wsl2"; echo "  ${C_OK}WSL2 detected${C_RST}"
    elif [[ "$(uname -s 2>/dev/null)" == "Darwin" ]]; then
        PLATFORM="macos"; echo "  ${C_OK}macOS detected${C_RST}"
    elif [[ "$(uname -s 2>/dev/null)" == "Linux" ]]; then
        PLATFORM="linux"; echo "  ${C_OK}Linux detected${C_RST}"
    else
        PLATFORM="unknown"; echo "  ${C_WARN}unknown platform ($(uname -s))${C_RST}"
    fi
    echo "  $(uname -a)"
}

apt_install() {
    if command -v apt-get >/dev/null 2>&1; then
        sudo -n apt-get install -y "$@" 2>&1 | tail -5 || apt-get install -y "$@" 2>&1 | tail -5
    fi
}

check_or_install_tools() {
    step "System tools"
    local missing=()
    for tool in clang clang++ make tar curl git; do
        if ! command -v "$tool" >/dev/null 2>&1; then
            missing+=("$tool")
        fi
    done
    if [[ ${#missing[@]} -eq 0 ]]; then
        pass "tools" "all present"
    else
        info "Missing: ${missing[*]}"
        if [[ "$PLATFORM" == "linux" || "$PLATFORM" == "wsl2" ]]; then
            info "Installing via apt..."
            apt_install clang lld cmake git curl make ca-certificates 2>&1 | tail -3
            for tool in clang clang++ git curl make; do
                if ! command -v "$tool" >/dev/null 2>&1; then
                    fail "tools" "$tool still missing after install"
                    return 1
                fi
            done
            pass "tools" "installed via apt"
        else
            fail "tools" "missing and not auto-installable on $PLATFORM"
            return 1
        fi
    fi
}

# Find ld64.lld — LLVM's Mach-O linker.
setup_linker() {
    step "Mach-O linker (ld64.lld)"
    mkdir -p "$TOOLS_DIR"

    local candidates=(
        "/usr/lib/llvm-19/bin/ld64.lld"
        "/usr/lib/llvm-18/bin/ld64.lld"
        "/usr/lib/llvm-17/bin/ld64.lld"
        "/usr/lib/llvm-16/bin/ld64.lld"
        "/usr/lib/llvm-15/bin/ld64.lld"
        "/opt/homebrew/opt/llvm/bin/ld64.lld"
        "/usr/local/opt/llvm/bin/ld64.lld"
    )
    local ld64=""
    if command -v ld64.lld >/dev/null 2>&1; then
        ld64="$(command -v ld64.lld)"
    else
        for c in "${candidates[@]}"; do
            if [[ -x "$c" ]]; then ld64="$c"; break; fi
        done
    fi

    if [[ -z "$ld64" ]]; then
        info "ld64.lld not found. Installing lld..."
        if [[ "$PLATFORM" == "linux" || "$PLATFORM" == "wsl2" ]]; then
            apt_install lld 2>&1 | tail -3
        elif [[ "$PLATFORM" == "macos" ]] && command -v brew >/dev/null 2>&1; then
            brew install llvm 2>&1 | tail -3
        fi
        for c in "${candidates[@]}"; do
            if [[ -x "$c" ]]; then ld64="$c"; break; fi
        done
    fi

    if [[ -z "$ld64" ]]; then
        fail "linker" "ld64.lld not found. Install LLVM 15+ (apt: lld)."
        return 1
    fi

    # Expose via standard name so clang can find it
    if [[ ! -e "$TOOLS_DIR/ld64.lld" ]]; then
        ln -sf "$ld64" "$TOOLS_DIR/ld64.lld"
    fi
    pass "linker" "ld64.lld -> $ld64"
}

build_ldid() {
    step "Build ldid (from source)"
    if [[ -x "$TOOLS_DIR/ldid" ]]; then
        info "Already present at $TOOLS_DIR/ldid"
        pass "ldid" "already built"
        return 0
    fi

    if [[ "$PLATFORM" == "linux" || "$PLATFORM" == "wsl2" ]]; then
        apt_install "${LDID_BUILD_DEPS_LINUX[@]}" 2>&1 | tail -3
    fi

    local tmp
    tmp="$(mktemp -d)"
    if ! git clone --depth=1 "$LDID_REPO" "$tmp/ldid" 2>&1 | tail -3; then
        fail "ldid" "git clone failed (no internet?)"
        rm -rf "$tmp"
        return 1
    fi
    if ! make -C "$tmp/ldid" 2>&1 | tail -3; then
        fail "ldid" "make failed"
        rm -rf "$tmp"
        return 1
    fi
    cp "$tmp/ldid/ldid" "$TOOLS_DIR/ldid"
    chmod +x "$TOOLS_DIR/ldid"
    rm -rf "$tmp"
    pass "ldid" "$TOOLS_DIR/ldid"
}

setup_sdk() {
    if [[ "$SKIP_SDK" == "1" ]]; then
        step "macOS SDK (skipped)"
        warn "sdk" "skipped via --skip-sdk"
        return 0
    fi

    step "macOS SDK extraction"
    mkdir -p "$SDK_DIR"

    # Already extracted? Check both index.json AND a valid SDKSettings.plist.
    local index="$SDK_DIR/index.json"
    if [[ -f "$SDK_DIR/MacOSX11.3.sdk/SDKSettings.plist" ]]; then
        info "SDK already extracted at $SDK_DIR/MacOSX11.3.sdk"
        pass "sdk" "already extracted"
        return 0
    fi
    if [[ -f "$index" ]]; then
        if $PYTHON_BIN -c "
import json, os
data = json.load(open('$index'))
sys_ok = any(os.path.exists(d.get('path', '')) and os.path.exists(os.path.join(d['path'], 'SDKSettings.plist')) for d in data)
sys.exit(0 if sys_ok else 1)
" 2>/dev/null; then
            info "SDK already installed per $index"
            pass "sdk" "already extracted"
            return 0
        fi
    fi

    # Look for a tarball in the SAD home or current dir
    local tarball=""
    for cand in "$SDK_DIR/MacOSX11.3.sdk.tar.xz" "$SAD_HOME/MacOSX11.3.sdk.tar.xz" "./MacOSX11.3.sdk.tar.xz"; do
        if [[ -f "$cand" ]]; then tarball="$cand"; break; fi
    done

    if [[ -z "$tarball" ]]; then
        info "No local tarball. Downloading..."
        if command -v curl >/dev/null 2>&1; then
            curl -fL -o "$SDK_DIR/MacOSX11.3.sdk.tar.xz" "$SDK_TARBALL_URL_DEFAULT" 2>&1 | tail -3
            tarball="$SDK_DIR/MacOSX11.3.sdk.tar.xz"
        else
            fail "sdk" "no curl and no local tarball"
            return 1
        fi
    fi

    if [[ ! -f "$tarball" ]]; then
        fail "sdk" "tarball not found: $tarball"
        return 1
    fi

    info "Extracting $tarball..."
    local extract_dir="$SDK_DIR/extract"
    rm -rf "$extract_dir"
    mkdir -p "$extract_dir"
    if ! tar -xJf "$tarball" -C "$extract_dir" 2>&1 | tail -3; then
        fail "sdk" "tar extract failed"
        return 1
    fi

    # Find the actual SDK root (look for SDKSettings.plist)
    local sdk_root=""
    sdk_root="$(find "$extract_dir" -name SDKSettings.plist -type f 2>/dev/null | head -1 | xargs -r dirname)"
    if [[ -z "$sdk_root" ]]; then
        fail "sdk" "SDKSettings.plist not found in tarball"
        return 1
    fi

    # Move to $SDK_DIR/MacOSX11.3.sdk
    rm -rf "$SDK_DIR/MacOSX11.3.sdk"
    mkdir -p "$SDK_DIR/MacOSX11.3.sdk"
    # Copy contents (not the dir itself, so the inner MacOSX11.3.sdk dir becomes the root)
    cp -a "$sdk_root/." "$SDK_DIR/MacOSX11.3.sdk/"

    # Update index.json
    python3 - <<PYEOF
import json, os
idx = "$SDK_DIR/index.json"
entry = {"version": "11.3", "platform": "macosx", "path": "$SDK_DIR/MacOSX11.3.sdk", "sha256": ""}
data = []
if os.path.exists(idx):
    try: data = json.load(open(idx))
    except: data = []
data = [d for d in data if not (d.get("platform") == "macosx" and d.get("version") == "11.3")]
data.append(entry)
json.dump(data, open(idx, "w"), indent=2)
PYEOF

    pass "sdk" "$SDK_DIR/MacOSX11.3.sdk"
}

install_sad() {
    step "Install smart-apple-dev"
    if [[ "$USE_LOCAL" == "1" && -d "./smart-apple-dev" ]]; then
        info "Installing local checkout..."
        if ! $PYTHON_BIN -m pip install --user -e "./smart-apple-dev" 2>&1 | tail -3; then
            $PYTHON_BIN -m pip install --break-system-packages -e "./smart-apple-dev" 2>&1 | tail -3
        fi
    else
        info "Installing from PyPI..."
        # Try user install first, fall back to system with --break-system-packages
        if ! $PYTHON_BIN -m pip install --user "smart-apple-dev" 2>&1 | tail -3; then
            $PYTHON_BIN -m pip install --break-system-packages "smart-apple-dev" 2>&1 | tail -3
        fi
    fi
    if ! $PYTHON_BIN -m smartapple.cli.app --version >/dev/null 2>&1 \
       && ! command -v smart-apple-dev >/dev/null 2>&1; then
        fail "sad-install" "smart-apple-dev not found after install"
        return 1
    fi
    pass "sad-install" "smart-apple-dev ready"
}

# Build a PATH that includes our tools dir plus standard bin locations
build_path() {
    local extra="$TOOLS_DIR:$HOME/.local/bin:$HOME/.cargo/bin"
    if [[ "$PLATFORM" == "linux" || "$PLATFORM" == "wsl2" ]]; then
        extra="$extra:/usr/local/bin:/usr/local/sbin:/usr/bin:/usr/sbin:/bin:/sbin"
    elif [[ "$PLATFORM" == "macos" ]]; then
        extra="$extra:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
    fi
    echo "$extra"
}

test_language() {
    local lang="$1"
    local sad_cli="smart-apple-dev"
    local proj="/tmp/sad-verify-$lang-$$"
    mkdir -p "$proj"
    cd "$proj" || return 1

    # init
    if ! $sad_cli init app --lang "$lang" >/dev/null 2>&1; then
        fail "$lang" "init failed"
        cd /; rm -rf "$proj"; return 1
    fi

    # flip target to macos
    local toml="app/smartapple.toml"
    if [[ ! -f "$toml" ]]; then
        fail "$lang" "smartapple.toml missing after init"
        cd /; rm -rf "$proj"; return 1
    fi
    sed -i 's/target = "ios"/target = "macos"/' "$toml"

    # build (from inside the project dir)
    cd "$proj/app" || { fail "$lang" "cannot cd into app dir"; cd /; rm -rf "$proj"; return 1; }
    local build_err
    if ! build_err="$($sad_cli build --target macos 2>&1)"; then
        fail "$lang" "build failed: $(echo "$build_err" | tail -3 | tr '\n' ' ')"
        cd /; rm -rf "$proj"; return 1
    fi

    # sign + ipa
    if ! $sad_cli sign --mode ad-hoc --ipa --target macos >/dev/null 2>&1; then
        fail "$lang" "sign/ipa failed"
        cd /; rm -rf "$proj"; return 1
    fi

    local ipa="build/macos/app.ipa"
    if [[ ! -f "$ipa" ]] || [[ ! -s "$ipa" ]]; then
        fail "$lang" "ipa not produced or empty"
        cd /; rm -rf "$proj"; return 1
    fi

    pass "$lang" "ipa $(stat -c%s "$ipa" 2>/dev/null || stat -f%z "$ipa") bytes"
    cd /
    rm -rf "$proj"
}

main() {
    echo "smart-apple-dev verification"
    echo "  SAD_HOME=$SAD_HOME"
    echo "  USE_LOCAL=$USE_LOCAL"
    echo "  LANG_FILTER=$LANGS_FILTER"
    detect_platform
    check_or_install_tools || exit 1
    setup_linker || exit 1
    build_ldid || true
    setup_sdk || true
    install_sad || exit 1

    # Make our tools visible to the CLI
    export PATH="$(build_path):$PATH"

    # Decide which binary to call
    if command -v smart-apple-dev >/dev/null 2>&1; then
        : # use system CLI
    else
        # Wrap python -m
        cat >"$TOOLS_DIR/smart-apple-dev" <<EOF
#!/usr/bin/env bash
exec $PYTHON_BIN -m smartapple.cli.app "\$@"
EOF
        chmod +x "$TOOLS_DIR/smart-apple-dev"
    fi

    step "Per-language smoke test"
    for lang in "${LANGS[@]}"; do
        case "$lang" in
            objc)  test_language objc ;;
            cpp)   test_language cpp ;;
            rust)
                if command -v cargo >/dev/null 2>&1; then
                    if command -v rustup >/dev/null 2>&1; then
                        rustup target add aarch64-apple-darwin 2>&1 | tail -2 || true
                    fi
                    test_language rust
                else
                    warn "rust" "cargo not installed; skipping"
                fi
                ;;
            go)
                if command -v go >/dev/null 2>&1; then
                    test_language go
                else
                    warn "go" "go not installed; skipping"
                fi
                ;;
            swift)
                if command -v swift >/dev/null 2>&1 || command -v xtool >/dev/null 2>&1; then
                    test_language swift
                else
                    warn "swift" "swift not installed (xtool also absent); skipping"
                fi
                ;;
            kotlin)
                # Kotlin can build for iOS/macOS (Kotlin/Native) or Android.
                # If ANDROID_HOME is set, run the dedicated Android path;
                # otherwise fall back to Kotlin/Native.
                if [[ -n "${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}" ]] && command -v java >/dev/null 2>&1; then
                    step "  kotlin: Android path (delegating to verify-android.sh)"
                    if [[ -x "${SCRIPT_DIR:-.}/verify-android.sh" ]]; then
                        # Pass through the install-mode flag
                        if [[ "$USE_LOCAL" == "1" ]]; then
                            "${SCRIPT_DIR:-.}/verify-android.sh" --local --skip-sdk
                        else
                            "${SCRIPT_DIR:-.}/verify-android.sh" --skip-sdk
                        fi
                    else
                        warn "kotlin" "verify-android.sh not found or not executable"
                    fi
                elif command -v kotlinc >/dev/null 2>&1; then
                    test_language kotlin
                else
                    warn "kotlin" "no Android SDK and no kotlinc; skipping"
                fi
                ;;
            *) warn "$lang" "unknown language" ;;
        esac
    done

    step "Summary"
    echo "  PASS=$PASS  FAIL=$FAIL  WARN=$WARN"
    if [[ $FAIL -gt 0 ]]; then
        echo
        echo "${C_FAIL}FAILED checks:${C_RST}"
        for k in "${!RESULTS[@]}"; do
            if [[ "${RESULTS[$k]}" == FAIL* ]]; then
                echo "  - $k: ${RESULTS[$k]#FAIL|}"
            fi
        done
        exit 1
    fi
    echo "${C_OK}ALL CHECKS PASSED${C_RST}"
    exit 0
}

main "$@"
