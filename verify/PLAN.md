# Plan: Seamlessness for Future iOS/macOS Projects

> Built from the ground truth of `verify.sh` (Linux passes 9/9) and
> the current state of `~/smart-apple-dev` on this Parrot Linux host.

## 0. Where we are today (baseline)

| Layer | Status | Evidence |
|---|---|---|
| Linux host: clang + ld64.lld + ldid + MacOSX11.3 SDK | ✅ works | `verify.sh` PASS=9 FAIL=0 |
| `init/build/sign/ipa` for objc, cpp, rust, go | ✅ works | real Mach-O inside real `.app`, signed by ldid, real `.ipa` |
| Windows host via WSL2 | ✅ documented | `verify/WINDOWS.md`, `verify/setup-windows.ps1`, `docs/windows.md` |
| CI (ubuntu-latest, Python 3.11–3.13) | ✅ works | `.github/workflows/ci.yml` ruff+pytest+codecov, plus Android job |
| 175 tests pass, 24 new verify-and-docs tests | ✅ works | `tests/test_verify_and_docs.py` |
| `init/build/sign/ipa` for **kotlin** | ⚠️ partial | `kotlin` template has gradle but the language isn't in `--lang` choices of the working CLI path — only runs via `verify-android.sh` |
| `init/build/sign/ipa` for **swift** | ⚠️ partial | needs `xtool` or `swift` (not on this host) |
| Empty templates (godot, unity, capacitor, expo, flutter, react-native, metal, scenekit, spritekit, tvos, unreal, visionos, watchos, ios, macos, swiftui) | ❌ | directory exists, no source, no `smartapple.toml` (or only toml) |
| iOS device install (libimobiledevice + USB) | ⚠️ | `verify.sh` has it commented; never tested on this host |
| macOS notarization | ❌ | needs Mac; only documented |
| `doctor --install` for Apple pieces | ❌ | xtool/cctools/swift install never automated |
| Doc site (mkdocs) | ✅ works | `docs/` has 18 pages, GitHub Pages deploys |

## 1. Goals (what seamlessness means)

A future developer — or another agent — should be able to:

1. **Create** a new iOS/macOS app or game in <60 s (`smart-apple-dev init`).
2. **Build, sign, and package** it locally without further configuration if the host is Linux/WSL.
3. **Iterate** with `build --release`, `sign --mode identity`, `install` to a device, all in one command.
4. **Ship** to TestFlight or App Store with a single `provider cloud` switch (or a `notarize` step on macOS).
5. **Verify** any future change to the toolchain with one command (`./verify/verify.sh`).
6. **Read** the docs without leaving the terminal (`smart-apple-dev docs` or `mkdocs serve`).

## 2. Workstreams (concrete, evidence-backed)

### A. Fill the template gaps (priority: HIGH)

Real cost today: someone runs `init --lang godot` or `--lang unity` and gets a broken project.

- **A.1** Decide which empty/partial templates are real. The 22 directories
  fall into three buckets:
  - **Real, working** (already proven): `objc`, `cpp`, `rust`, `go`, `kotlin` (via verify-android.sh)
  - **Real but stubbed** (smartapple.toml only): `godot`, `unity`
  - **Empty** (no source, no config): `capacitor`, `expo`, `flutter`, `react-native`, `metal`, `scenekit`, `spritekit`, `tvos`, `unreal`, `visionos`, `watchos`, `ios`, `macos`, `swiftui`
- **A.2** For the **stubbed** templates: add a real entry point.
  - `godot/`: ship a minimal `project.godot` + `Main.tscn` + a Godot 4 export
    preset (`export_presets.cfg`) that targets macOS and iOS. Reference
    `games/Godot_v4.2.2-stable_linux.x86_64` (already on disk) for the engine.
  - `unity/`: ship a minimal `Assets/Scenes/SampleScene.unity` + a C# script
    + build instructions; or remove it and redirect to `examples/hello-kotlin`.
- **A.3** For the **empty** templates: either ship a real working scaffold
  or delete the directory. An empty `templates/ios/` is worse than no entry.
- **A.4** Add a **smoke test** in `test_templates.py` that runs
  `init` + `build` (when compiler is present) for every real template, and
  asserts `init` produces a parseable `smartapple.toml` for every listed
  language. This catches future template rot.

### B. Make `smart-apple-dev` self-bootstrap (priority: HIGH)

Today: `verify.sh` does the bootstrap (install clang, lld, ldid, SDK, sad).
But a new developer running just `pip install smart-apple-dev` and trying
to build gets `doctor --install` failures for xtool/cctools/swift, with
no real auto-install.

- **B.1** Make `doctor --install` actually install `lld` on Debian/Ubuntu
  (it currently just prints the apt package name; `install_all` calls
  `install_fn` which is `install_ldid`/`install_xtool`/`install_cctools`
  — extend the pattern to wrap `apt install lld clang cmake`).
- **B.2** Auto-add Rust Apple targets on first `build --target macos`
  (the verify.sh path already does this; `rust.py` should too). If
  `rustup` is present, run `rustup target add aarch64-apple-darwin`
  the first time and cache the result.
- **B.3** On `init`, if no SDK is installed, prompt the user:
  > "No macOS SDK installed. Run `smart-apple-dev sdk install macosx 14.0`
  > to download (~600 MB)? [y/N]"
  This replaces the current silent failure.

### C. `install` and `notarize` paths (priority: MEDIUM)

- **C.1** Wire `smart-apple-dev install` to actually call
  `ideviceinstaller` on Linux when the user is signed into a developer
  account. Today the device module exists but the install path is
  untested end-to-end. Add a smoke test that runs the install path
  with a fake `ideviceinstaller` and asserts the right command.
- **C.2** Add a `smart-apple-dev notarize` command that:
  - On macOS: runs `xcrun notarytool submit` and `xcrun stapler staple`.
  - On Linux/Windows: prints "Notarization requires a Mac; see
    `smart-apple-dev notarize --remote <user@host>` to SSH into a
    remote Mac" and uses the existing `SSHProvider` plumbing.
- **C.3** Add a `provider cloud` shortcut for EAS / BuildJet so a
  user can write `smart-apple-dev build --provider eas --target ios`
  and have the build happen on cloud macOS without owning a Mac.

### D. CI expansion (priority: MEDIUM)

Today: `ci.yml` runs `pytest` on Linux. It does **not** run `verify.sh`.

- **D.1** Add a `verify` job to `ci.yml` that runs `./verify/verify.sh`
  on every PR. This catches regressions in the actual build pipeline,
  not just the unit tests. Pin to a small `flutter`-free subset if the
  job gets too slow.
- **D.2** Add a `verify-windows` job that uses
  `microsoft/playwright` (or a custom WSL-on-ubuntu Docker image) to
  run verify.sh inside a WSL-equivalent Ubuntu. Closer to the real
  Windows user path.
- **D.3** Add a `release` gate: `verify.sh` must pass before
  `release.yml` will publish to PyPI.

### E. Docs seamlessness (priority: LOW but easy)

- **E.1** Add `smart-apple-dev docs` that opens the local mkdocs site
  in the user's browser (`python -m http.server` on port 8000 with
  `mkdocs serve` underneath).
- **E.2** Add a `templates/GUIDE.md` documenting which templates are
  real, which are stubs, and how to add a new one.
- **E.3** Add a `CONTRIBUTING-template.md` so a future contributor
  adding a new language template knows what to ship:
  `smartapple.toml` + main source + run via `verify.sh`.

### F. Project-bootstrap helper (priority: MEDIUM, ships today)

- **F.1** Add a `smart-apple-dev new <name> --lang <L>` alias for `init`
  that:
  - Runs `init`
  - Runs `build` once to confirm the toolchain
  - Prints the next steps (`sign --ipa`, `install`, `notarize`)
  - Optionally opens the docs for that language
- **F.2** Add a `smart-apple-dev doctor --json` output for tooling
  (e.g., agents that want to know what's installed).

## 3. Sequencing (what to do this week vs. next)

| Day | Workstream | Concrete task | Acceptance |
|---|---|---|---|
| 1 | A.1+A.4 | Audit templates, add template-parse test | `pytest tests/test_templates.py` passes, lists real vs stub |
| 1 | A.2 | Ship a real `templates/godot/` with `project.godot` + `Main.tscn` + export preset | `godot --headless --check-only templates/godot/project.godot` exits 0 |
| 2 | A.3 | Delete or fill empty templates (decision: keep `tvos/watchos/visionos` with stub `Sources/` + README; delete the rest) | No `templates/X/` with 0 files |
| 2 | B.1 | Wire `doctor --install` for `lld`/`clang`/`cmake` on Debian | `apt-get install lld` runs as part of `doctor --install` |
| 3 | B.2 | `rust.py` calls `rustup target add` automatically on first Apple build | Fresh host → `build --target macos` succeeds without manual `rustup` step |
| 3 | B.3 | `init` prompts when SDK missing | First-time user gets a clear "install SDK?" prompt |
| 4 | D.1 | Add `verify` job to `ci.yml` | PR shows green check from `./verify/verify.sh` |
| 5 | C.2 | `notarize` command + remote fallback | `smart-apple-dev notarize --help` shows both local and remote paths |
| 5 | F.1 | `smart-apple-dev new` alias | `new myapp --lang objc` does init + build + shows next steps |

## 4. Risks (what could blow up)

- **iOS SDK extraction on Windows/WSL** — verify.sh works on Linux; WSL
  is similar enough but untested in CI. Add a Windows runner step before
  claiming full cross-platform.
- **`rustup target add` is interactive** in some setups. The current
  verify.sh invocation uses `tail -2` to swallow prompts; pin to
  non-interactive mode (`rustup target add --toolchain stable`).
- **CI time** — `verify.sh` takes ~40 s on this host. Adding it to
  every PR is fine, but the docker test from earlier took >5 min
  (network-bound). Don't put the docker test in PR; only nightly.
- **Apple SDK distribution** — the tarball URL in `verify.sh` is
  from `phracker/MacOSX-SDKs`. If that repo is DMCA'd or moved
  (it has been before), `verify.sh` breaks. Pin to a specific
  release tag, not `main`.
- **CocoaPods** — `templates/objc/Podfile` references `pod install`
  which isn't part of verify.sh. If a user adds Firebase via
  `templates/objc`, they need CocoaPods. Document this.

## 5. Definition of done

For "future projects work smooth" to be true, a brand-new user
on a fresh Linux (or WSL) box should be able to:

```bash
git clone https://github.com/realstreetsmartnyc/smart-apple-dev
cd smart-apple-dev
./verify/verify.sh                     # green
cd examples/hello-objc                 # or `smart-apple-dev new myapp --lang objc`
smart-apple-dev build --target macos   # green
smart-apple-dev sign --mode ad-hoc --ipa
unzip -l build/macos/hello.ipa         # real IPA, real .app inside
```

If that flow takes more than 5 minutes including the SDK download,
the goal is not yet met. Today it takes ~6 minutes here, so we're
**close but not done** — the gaps are mostly in B.1 (doctor
auto-install) and the template completeness audit (A).

## 6. Don't do

- **Don't** build a web-based installer. The CLI + verify.sh is
  the right level of abstraction.
- **Don't** chase App Store / notarization automation that requires
  owning a Mac. The honest answer is "remote Mac worker", and we
  should say so clearly in the docs.
- **Don't** delete the empty templates silently. Some users have
  scripts that reference `templates/ios/`. Migrate them first.
- **Don't** add more languages to the CLI `--lang` list until they
  have a real working template. `--lang` should be the contract
  that "this works today".
