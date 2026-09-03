#!/usr/bin/env bash
# 60-second demo: scaffold -> build -> sign -> IPA
# Run from repo root: bash scripts/demo.sh
# Requires: pip install -e .  (or smart-apple-dev on PATH)
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if command -v smart-apple-dev &>/dev/null; then
  run_cli() { smart-apple-dev "$@"; }
else
  run_cli() { PYTHONPATH="$REPO_DIR/src" python3 -m smartapple.cli_main "$@"; }
fi

echo "==> smart-apple-dev demo (60s)"
echo ""

echo "--- 1. System check ---"
run_cli doctor 2>&1 | head -20
echo ""

echo "--- 2. Scaffold ---"
TMPDIR=$(mktemp -d)
echo "Working in: $TMPDIR"
cd "$TMPDIR"
run_cli init hello --lang objc
ls -R hello | head -20
echo ""

echo "--- 3. Build ---"
cd hello
run_cli build --target macos 2>&1 | tail -20
echo ""

echo "--- 4. Sign + IPA ---"
run_cli sign --mode ad-hoc --target macos --ipa 2>&1 | tail -20
echo ""

echo "--- 5. Result ---"
ls -lh build/macos/*.ipa 2>/dev/null || ls -lh build/macos/ 2>/dev/null | head -20
echo ""
echo "Demo done. IPA at: $TMPDIR/hello/build/macos/hello.ipa"
echo "Clean up: rm -rf $TMPDIR"

# Optional: Android path (only if ANDROID_HOME is set and --target android was requested)
if [ "${SMART_DEMO_ANDROID:-0}" = "1" ] && [ -n "${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}" ]; then
  echo ""
  echo "--- 6. Android build (Kotlin) ---"
  TMPDIR2=$(mktemp -d)
  cd "$TMPDIR2"
  run_cli init hello-kt --lang kotlin || true
  if [ -d hello-kt ]; then
    cd hello-kt
    run_cli build --target android 2>&1 | tail -20 || true
    ls -lh build/outputs/apk/debug/ 2>/dev/null | head -10 || true
    echo "Clean up: rm -rf $TMPDIR2"
  fi
fi
