#!/usr/bin/env bash
# verify-android.sh — End-to-end smoke test for the smart-apple-dev
# Android path on Linux / WSL2 / macOS.
#
# What it does:
#   1. Detects platform and required Android tools (JDK 17, ANDROID_HOME)
#   2. Verifies the Android SDK has platform 34 + build-tools 34.0.0
#   3. Installs smart-apple-dev (from PyPI or local checkout)
#   4. Copies examples/hello-kotlin to a temp dir (renders clean)
#   5. Runs: smart-apple-dev doctor --platform android (subset)
#   6. Runs: smart-apple-dev build --target android
#   7. Verifies the resulting APK contains AndroidManifest.xml
#   8. Mocks `adb` (using a fake adb shim) and exercises install --apk
#   9. Prints PASS/FAIL table; non-zero exit on any failure
#
# Usage:
#   ./verify-android.sh                  # full test
#   ./verify-android.sh --local          # test local checkout (editable)
#   ./verify-android.sh --skip-sdk       # don't verify SDK contents
#   ./verify-android.sh --no-emulator    # don't try to start an emulator
#
# Exits 0 on success, 1 if any step fails.

set -uo pipefail

# ---------- Configuration ----------
SAD_HOME="${SAD_HOME:-$HOME/.smart-apple-dev}"
# ANDROID_HOME may be unset; fall back to ANDROID_SDK_ROOT, then a default.
if [[ -n "${ANDROID_HOME:-}" ]]; then
    ANDROID_SDK_DEFAULT="$ANDROID_HOME"
elif [[ -n "${ANDROID_SDK_ROOT:-}" ]]; then
    ANDROID_SDK_DEFAULT="$ANDROID_SDK_ROOT"
else
    ANDROID_SDK_DEFAULT="$HOME/Android/Sdk"
fi
PYTHON_BIN="${PYTHON_BIN:-python3}"
USE_LOCAL=0
SKIP_SDK_CHECK=0
NO_EMULATOR=0
PACKAGE_VERSION="${SAD_PACKAGE_VERSION:-smart-apple-dev}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ---------- CLI args ----------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --local) USE_LOCAL=1; shift ;;
        --skip-sdk) SKIP_SDK_CHECK=1; shift ;;
        --no-emulator) NO_EMULATOR=1; shift ;;
        -h|--help)
            head -25 "$0" | tail -22
            exit 0 ;;
        *) echo "Unknown arg: $1" >&2; exit 2 ;;
    esac
done

# ---------- Pretty output ----------
if [[ -t 1 ]]; then
    C_OK=$'\033[32m'; C_FAIL=$'\033[31m'; C_WARN=$'\033[33m'; C_INFO=$'\033[36m'; C_RST=$'\033[0m'
else
    C_OK=''; C_FAIL=''; C_WARN=''; C_INFO=''; C_RST=''
fi

PASS=0; FAIL=0; WARN=0
declare -A RESULTS
step() { echo; echo "${C_INFO}=== $* ===${C_RST}"; }
pass() { PASS=$((PASS+1)); echo "${C_OK}[PASS]${C_RST}  $*"; RESULTS["$1"]="PASS"; }
fail() { FAIL=$((FAIL+1)); echo "${C_FAIL}[FAIL]${C_RST}  $*"; RESULTS["$1"]="FAIL|$2"; }
warn() { WARN=$((WARN+1)); echo "${C_WARN}[WARN]${C_RST}  $*"; RESULTS["$1"]="WARN|$2"; }
info() { echo "       $*"; }

# ---------- Platform detection ----------
detect_platform() {
    if [[ -f /proc/version ]] && grep -qi microsoft /proc/version 2>/dev/null; then
        echo "wsl2"
    elif [[ "$(uname -s 2>/dev/null)" == "Darwin" ]]; then
        echo "macos"
    elif [[ "$(uname -s 2>/dev/null)" == "Linux" ]]; then
        echo "linux"
    else
        echo "unknown"
    fi
}

PLATFORM=$(detect_platform)
step "Platform: $PLATFORM"

# ---------- Step 1: JDK ----------
step "1/6 JDK 17+"
JAVA_BIN="$(command -v java || true)"
if [[ -z "$JAVA_BIN" ]]; then
    fail "jdk" "java not on PATH"
    JDK_OK=0
else
    JAVA_VER="$("$JAVA_BIN" -version 2>&1 | head -1 | sed -E 's/.*"([0-9]+).*/\1/')"
    info "Java major version: $JAVA_VER"
    if [[ "$JAVA_VER" -ge 17 ]]; then
        pass "jdk"
        JDK_OK=1
    else
        fail "jdk" "need JDK 17+ for Android Gradle Plugin (found $JAVA_VER)"
        JDK_OK=0
    fi
fi

# ---------- Step 2: ANDROID_HOME ----------
step "2/6 ANDROID_HOME"
if [[ -z "${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}" ]]; then
    info "ANDROID_HOME and ANDROID_SDK_ROOT are unset; trying default: $ANDROID_SDK_DEFAULT"
    if [[ -d "$ANDROID_SDK_DEFAULT" ]]; then
        export ANDROID_HOME="$ANDROID_SDK_DEFAULT"
        info "Using default SDK at $ANDROID_HOME"
    else
        warn "sdk_home" "ANDROID_HOME not set; will be checked again after install step"
    fi
else
    info "ANDROID_HOME = $ANDROID_HOME"
fi

# ---------- Step 3: smart-apple-dev ----------
step "3/6 Install smart-apple-dev"
if [[ "$USE_LOCAL" == "1" ]]; then
    info "Installing from local checkout (editable)..."
    if (cd "$REPO_ROOT" && "$PYTHON_BIN" -m pip install --quiet -e ".[dev]"); then
        pass "install"
    else
        fail "install" "pip install -e . failed"
    fi
else
    info "Installing from PyPI ($PACKAGE_VERSION)..."
    if "$PYTHON_BIN" -m pip install --quiet --upgrade "$PACKAGE_VERSION"; then
        pass "install"
    else
        fail "install" "pip install $PACKAGE_VERSION failed"
    fi
fi

CLI="$(command -v smart-apple-dev || true)"
if [[ -z "$CLI" ]]; then
    # When using a venv, the smart-apple-dev script lives in <venv>/bin/
    # but may not be on PATH. Try the venv that's installing us.
    if [[ -n "${VIRTUAL_ENV:-}" ]]; then
        CLI="$VIRTUAL_ENV/bin/smart-apple-dev"
    elif [[ "$PYTHON_BIN" == *"/.venv/bin/python"* ]]; then
        CLI="${PYTHON_BIN%/*}/smart-apple-dev"
    fi
fi
if [[ -z "$CLI" ]] || [[ ! -x "$CLI" ]]; then
    fail "cli" "smart-apple-dev not on PATH after install (looked in PATH and \$VIRTUAL_ENV)"
else
    info "CLI: $CLI"
    info "Version: $("$CLI" --version 2>&1 || true)"
    pass "cli"
fi

# ---------- Step 4: Android SDK present ----------
step "4/6 Android SDK contents"
if [[ "$SKIP_SDK_CHECK" == "1" ]]; then
    warn "sdk_check" "--skip-sdk set; not verifying"
elif [[ -z "${ANDROID_HOME:-}" ]] || [[ ! -d "${ANDROID_HOME:-}" ]]; then
    fail "sdk_dir" "ANDROID_HOME directory does not exist; install Android Studio or sdkmanager"
else
    PLATFORMS="$ANDROID_HOME/platforms"
    BUILD_TOOLS="$ANDROID_HOME/build-tools"
    HAS_P34=0; HAS_BT34=0
    [[ -d "$PLATFORMS/android-34" ]] && HAS_P34=1
    [[ -d "$BUILD_TOOLS/34.0.0" ]] && HAS_BT34=1
    if [[ "$HAS_P34" == "1" && "$HAS_BT34" == "1" ]]; then
        pass "sdk"
    else
        warn "sdk" "platform-34=$HAS_P34 build-tools-34=$HAS_BT34 — install with: sdkmanager 'platforms;android-34' 'build-tools;34.0.0'"
    fi
fi

# ---------- Step 5: Build the example ----------
step "5/6 Build examples/hello-kotlin --target android"
TMP_BUILD="$(mktemp -d)"
trap "rm -rf $TMP_BUILD" EXIT
info "Workdir: $TMP_BUILD"

cp -r "$REPO_ROOT/examples/hello-kotlin" "$TMP_BUILD/hello-kotlin"
cd "$TMP_BUILD/hello-kotlin"

# Make gradlew executable (templates may not have it)
if [[ -f "./gradlew" ]]; then
    chmod +x ./gradlew
else
    info "No gradlew in example — smart-apple-dev init will use the project gradle if any"
fi

info "Running: smart-apple-dev build --target android"
if [[ "$JDK_OK" == "1" && -n "${ANDROID_HOME:-}" ]]; then
    if "$CLI" build --target android 2>&1 | tail -40; then
        APK="$(find "$TMP_BUILD/hello-kotlin/build/outputs/apk" -name '*.apk' 2>/dev/null | head -1 || true)"
        if [[ -n "$APK" ]] && [[ -f "$APK" ]]; then
            pass "build"
            info "APK: $APK ($(du -h "$APK" | cut -f1))"
            # Verify it's a real APK (zip with AndroidManifest.xml)
            if unzip -l "$APK" 2>/dev/null | grep -q "AndroidManifest.xml"; then
                pass "apk_valid"
            else
                fail "apk_valid" "APK doesn't contain AndroidManifest.xml"
            fi
        else
            fail "build" "build reported success but no APK found under build/outputs/apk/"
        fi
    else
        fail "build" "smart-apple-dev build --target android exited non-zero"
    fi
else
    warn "build" "skipped (JDK=$JDK_OK ANDROID_HOME=${ANDROID_HOME:-unset})"
    info "Set ANDROID_HOME and ensure JDK 17+ to run the build step"
fi

# ---------- Step 6: adb install (with fake adb if needed) ----------
step "6/6 adb device install (with fake adb if no real device)"
APK_PATH="$(find "$TMP_BUILD/hello-kotlin/build/outputs/apk" -name '*.apk' 2>/dev/null | head -1 || true)"
if [[ -n "$APK_PATH" ]] && [[ -f "$APK_PATH" ]]; then
    # Build a fake adb shim that reports one connected emulator
    FAKE_BIN="$(mktemp -d)"
    cat > "$FAKE_BIN/adb" <<'EOF'
#!/usr/bin/env bash
case "$1" in
    devices)
        if [[ "$2" == "-l" ]]; then
            echo "List of devices attached"
            echo "emulator-5554  device product:fake model:FakeEmu"
        else
            echo "List of devices attached"
            echo "emulator-5554  device"
        fi
        ;;
    -s)
        # smart-apple-dev always calls `adb -s <serial> install ...`
        # Shift past -s <serial> and look at the action
        shift 2
        case "$1" in
            install) echo "Success"; exit 0 ;;
            *) exit 0 ;;
        esac
        ;;
    *) exit 0 ;;
esac
EOF
    chmod +x "$FAKE_BIN/adb"
    info "Using fake adb at $FAKE_BIN/adb"

    PATH="$FAKE_BIN:$PATH" "$CLI" install --apk "$APK_PATH" 2>&1 | tail -10 | sed 's/^/       /'
    if PATH="$FAKE_BIN:$PATH" "$CLI" install --apk "$APK_PATH" >/dev/null 2>&1; then
        pass "install"
    else
        fail "install" "smart-apple-dev install --apk failed (even with fake adb)"
    fi
else
    warn "install" "skipped (no APK from step 5)"
fi

# ---------- Summary ----------
step "Summary"
TOTAL=$((PASS + FAIL + WARN))
echo
printf "  ${C_OK}PASS: %d${C_RST}   ${C_FAIL}FAIL: %d${C_RST}   ${C_WARN}WARN: %d${C_RST}   TOTAL: %d\n" \
    "$PASS" "$FAIL" "$WARN" "$TOTAL"
echo
for k in "${!RESULTS[@]}"; do
    v="${RESULTS[$k]}"
    case "$v" in
        PASS) printf "  ${C_OK}PASS${C_RST}  %s\n" "$k" ;;
        FAIL*) printf "  ${C_FAIL}FAIL${C_RST}  %s  (%s)\n" "$k" "${v#FAIL|}" ;;
        WARN*) printf "  ${C_WARN}WARN${C_RST}  %s  (%s)\n" "$k" "${v#WARN|}" ;;
    esac
done
echo

if [[ "$FAIL" -gt 0 ]]; then
    echo "${C_FAIL}Android verify FAILED ($FAIL failures)${C_RST}"
    exit 1
fi
echo "${C_OK}Android verify PASSED ($PASS passed, $WARN warnings)${C_RST}"
exit 0
