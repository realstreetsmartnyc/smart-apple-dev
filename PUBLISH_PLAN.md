# smart-apple-dev — Publish Readiness Plan

**Date:** 2026-09-01 | **Current Version:** 0.1.0 | **Target Version:** 1.0.0  
**Test Suite:** 68/68 passing | **Source Files:** 36 | **Lines:** ~4,100

---

## Primary Goal: Publish smart-apple-dev as production-ready v1.0.0

Deliver a cross-platform iOS/macOS development toolchain that can be installed via PyPI and used in production CI pipelines. Every command must be reliable, every backend testable, every bug fixed, and every piece of documentation accurate.

---

## Goal 1 — Fix All Known Bugs (4 bugs, ~30 min)

**Success criteria:** Zero known bugs. All template rendering correct. No dead code. No stubs that silently fail.

---

### Sub-goal 1.1: Remove duplicate `SdkError` class

**File:** `src/smartapple/core/sdk.py:19-21` (dead duplicate), `src/smartapple/core/sdk.py:203-205` (keep)  
**Impact:** Dead code removal. No functional change — both definitions are identical.  
**Risk:** Zero. Python always uses the last definition in the module.

**Plan:**
1. Delete lines 19-21 (the first `SdkError` definition)  
2. Delete the blank lines 22-24 that follow it  
3. Run `python3 -m pytest tests/test_sdk.py -v` to confirm all 10 SDK tests pass  

---

### Sub-goal 1.2: Fix Go template `go.mod` rendering

**File:** `templates/go/go.mod:1` — `module {NAME}` should be `module {{NAME}}`  
**Impact:** Go projects scaffold with `{NAME}` as literal module name instead of the actual project name.  
**Risk:** Zero. Straightforward string fix.

**Plan:**
1. Change `module {NAME}` to `module {{NAME}}` in `templates/go/go.mod`  
2. Add a test in `tests/test_templates.py` that calls `init` with `--lang go` and asserts `go.mod` contains the correct rendered name  
3. Run `python3 -m pytest tests/test_templates.py -v`  

---

### Sub-goal 1.3: Fix `RustBackend.ensure_target()` always returning `True`

**File:** `src/smartapple/build/rust.py:70-80`  
**Impact:** Rust builds fail late (at cargo invocation) instead of early (at backend check) when the iOS target isn't installed.  
**Risk:** Low. Logic change is scoped to one method.

**Plan:**
1. Parse `rustup target list --installed` stdout into a set of installed target triples  
2. Return `target_triple in installed_targets`  
3. Add a unit test in `tests/test_build_cpp.py` (or new `tests/test_build_rust.py`) mocking `run_cmd` to return simulated rustup output  
4. Run `python3 -m pytest tests/ -v`  

**Steps:**
```
Sub-sub-goal 1.3.1: Parse rustup output → set of target strings
Sub-sub-goal 1.3.2: Check target_triple membership
Sub-sub-goal 1.3.3: Write test with mocked run_cmd
Sub-sub-goal 1.3.4: Verify all existing tests still pass
```

---

### Sub-goal 1.4: Fix `submit_for_review()` silent stub

**File:** `src/smartapple/store/__init__.py:121-136`  
**Impact:** Users calling `submit_for_review()` get a misleading generic error instead of a clear "not yet implemented" message.  
**Risk:** Zero. This is a user-facing error message improvement.

**Plan:**
1. In `submit_for_review()`, check for fastlane availability as it already does  
2. If fastlane is available but no Fastfile exists, generate a temporary Fastfile with the `upload_to_app_store` lane (same pattern as `_upload_fastlane`) and add a `submit_for_review` action  
3. If fastlane is not available, return a clear `AscResult` with an actionable error message  
4. Add a test that calls `submit_for_review` without fastlane and asserts the error message is clear  
5. Run `python3 -m pytest tests/ -v`  

**Steps:**
```
Sub-sub-goal 1.4.1: Generate Fastfile with submit_for_review lane when fastlane exists
Sub-sub-goal 1.4.2: Return actionable AscResult when fastlane is missing
Sub-sub-goal 1.4.3: Add test for submit_for_review error paths
```

---

## Goal 2 — Git & Project Infrastructure (4 tasks, ~1 hr)

**Success criteria:** Git repo initialized with .gitignore. GitHub Actions CI runs tests on every push. README shows passing badge.

---

### Sub-goal 2.1: Initialize Git repository

**Plan:**
1. Create `.gitignore` covering: `__pycache__/`, `*.pyc`, `.pytest_cache/`, `*.egg-info/`, `dist/`, `build/`, `.env`, `*.swp`, `.DS_Store`  
2. Run `git init`  
3. `git add -A && git commit -m "Initial commit: smart-apple-dev v0.1.0 MVP"`  

**Steps:**
```
Sub-sub-goal 2.1.1: Write .gitignore with standard Python entries
Sub-sub-goal 2.1.2: git init + initial commit
```

---

### Sub-goal 2.2: Add GitHub Actions CI

**Plan:**
1. Create `.github/workflows/ci.yml`  
2. Matrix: Python 3.11, 3.12, 3.13 on ubuntu-latest  
3. Steps: checkout, install system deps (clang, lld, libimobiledevice), pip install -e ., pytest  
4. Add optional: install MacOSX SDK for C/ObjC integration tests, install ldid for signing tests  
5. Add lint step: `ruff check src/ tests/`  
6. Add type check step: `mypy src/`  
7. Update README.md with CI badge  

**Steps:**
```
Sub-sub-goal 2.2.1: Create ci.yml with test matrix and system deps
Sub-sub-goal 2.2.2: Add ruff linting step
Sub-sub-goal 2.2.3: Add mypy type checking step
Sub-sub-goal 2.2.4: Add SDK and ldid installation steps for integration tests
Sub-sub-goal 2.2.5: Add CI badge to README.md
```

---

### Sub-goal 2.3: Add linting configuration

**Plan:**
1. Add `ruff` as a dev dependency in `pyproject.toml`  
2. Configure `[tool.ruff]` with line-length=100, target-version=py311, select=["E","F","I","N","W","UP"]  
3. Add `[tool.ruff.lint.isort]` for import sorting  
4. Run `ruff check src/ tests/ --fix` and resolve any issues  
5. Add `lint` script to pyproject.toml `[project.scripts]` or document `ruff check` as the lint command  

**Steps:**
```
Sub-sub-goal 2.3.1: Add ruff dev dependency
Sub-sub-goal 2.3.2: Configure tool.ruff in pyproject.toml
Sub-sub-goal 2.3.3: Auto-fix all lint issues
Sub-sub-goal 2.3.4: Verify zero lint errors
```

---

### Sub-goal 2.4: Add type checking configuration

**Plan:**
1. Add `mypy` as a dev dependency  
2. Configure `[tool.mypy]` in pyproject.toml: python_version=3.11, strict=false initially, warn_return_any, warn_unused_configs  
3. Run `mypy src/` and fix type errors  
4. Gradual path: start with `check_untyped_defs = false`, then enable module by module  

**Steps:**
```
Sub-sub-goal 2.4.1: Add mypy dev dependency
Sub-sub-goal 2.4.2: Configure tool.mypy in pyproject.toml
Sub-sub-goal 2.4.3: Fix type errors file by file
Sub-sub-goal 2.4.4: Enable strict mode for at least core/ and build/ modules
```

---

## Goal 3 — Code Quality & Developer Experience (4 tasks, ~2 hr)

**Success criteria:** Structured logging throughout. Environment variables loaded from .env file. ARCHITECTURE.md matches actual code. All print() calls replaced.

---

### Sub-goal 3.1: Add structured logging

**Impact:** Currently every module uses `print()`. This mixes diagnostics with output, breaks `--quiet` mode, and prevents CI-friendly structured output.  
**Risk:** Medium. Every file that uses `print()` must be touched.

**Plan:**
1. Create `src/smartapple/core/logger.py` with a `get_logger()` function returning a `logging.Logger`  
2. Configure: `INFO` to stdout for user-facing output, `DEBUG` to stderr for diagnostics, support `--verbose`/`--quiet` flags via root logger level  
3. Replace all `print()` calls:
   - User-facing results → `logger.info()`  
   - Errors → `logger.error()`  
   - Warnings → `logger.warning()`  
   - Debug/tool output → `logger.debug()`  
4. Files to update: `cli/app.py`, `doctor.py`, `core/sdk.py`, `build/cpp.py`, `build/orchestrator.py`, `sign/__init__.py`, `device/__init__.py`, `store/__init__.py`, `agent/loop.py`, `agent/llm.py`  

**Steps:**
```
Sub-sub-goal 3.1.1: Create core/logger.py with get_logger()
Sub-sub-goal 3.1.2: Add --verbose / --quiet global CLI options
Sub-sub-goal 3.1.3: Replace print() in cli/app.py (highest priority, 501 lines)
Sub-sub-goal 3.1.4: Replace print() in doctor.py (341 lines)
Sub-sub-goal 3.1.5: Replace print() in build modules (cpp.py, orchestrator.py)
Sub-sub-goal 3.1.6: Replace print() in sign/, device/, store/, agent/ modules
Sub-sub-goal 3.1.7: Verify no regressions in 68 tests
```

---

### Sub-goal 3.2: Add .env file support

**Plan:**
1. Add `python-dotenv>=1.0` to `pyproject.toml` dependencies  
2. In `src/smartapple/cli/app.py` (or `cli_main.py`), add `from dotenv import load_dotenv; load_dotenv()` before importing agent modules  
3. Document expected env vars in README.md: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OLLAMA_URL`, `FASTLANE_USER`, `FASTLANE_PASSWORD`, `APP_STORE_CONNECT_API_KEY`  
4. Add `.env.example` file with commented-out placeholder values  

**Steps:**
```
Sub-sub-goal 3.2.1: Add python-dotenv dependency
Sub-sub-goal 3.2.2: Load .env at CLI startup in create_cli()
Sub-sub-goal 3.2.3: Create .env.example with all documented env vars
Sub-sub-goal 3.2.4: Update README.md with environment variables section
```

---

### Sub-goal 3.3: Fix ARCHITECTURE.md discrepancies

**Impact:** ARCHITECTURE.md references files that don't exist (`logger.py`, `ccpp.py` vs `cpp.py`, split sub-modules). Misleads contributors.

**Plan:**
1. Update file tree in ARCHITECTURE.md to match actual structure:
   - `core/logger.py` → exists after sub-goal 3.1  
   - `build/ccpp.py` → `build/cpp.py`  
   - `sign/signer.py + cert.py + provisioning.py` → `sign/__init__.py`  
   - `device/manager.py + install.py + launch.py` → `device/__init__.py`  
   - `store/asc.py + fastlane.py` → `store/__init__.py`  
2. Add note that modules are consolidated in single files for MVP simplicity and can be split later  

**Steps:**
```
Sub-sub-goal 3.3.1: Fix file references in ARCHITECTURE.md tree diagram
Sub-sub-goal 3.3.2: Fix file references in dependency section
Sub-sub-goal 3.3.3: Add consolidation note
```

---

### Sub-goal 3.4: Add `--json` output flag for machine readability

**Plan:**
1. Add `@click.option("--json", "output_json", is_flag=True)` to all commands that produce structured output: `build`, `sign`, `install`, `doctor`, `check`, `info`, `devices`, `sdk list`, `provider list`  
2. When `--json` is set, print `json.dumps(result.to_dict(), indent=2)` instead of human-readable text  
3. Ensure all result dataclasses have `to_dict()` methods (most already do: `BuildResult`, `SignResult`, `ProviderResult`, `AscResult`, `DoctorReport`)  

**Steps:**
```
Sub-sub-goal 3.4.1: Add --json flag to CLI commands
Sub-sub-goal 3.4.2: Verify all result types have to_dict()
Sub-sub-goal 3.4.3: Add integration test for JSON output on build/sign/doctor
```

---

## Goal 4 — Testing & Coverage (3 tasks, ~2 hr)

**Success criteria:** All backends have at least one integration test. Agent loop tested without real LLM. Coverage >80%. No regressions.

---

### Sub-goal 4.1: Add tests for untested backends

**Plan:**
1. Create `tests/test_build_rust.py`: mock `run_cmd` to return a simulated cargo build. Test target triple computation, release mode, cargo-not-found error path.  
2. Create `tests/test_build_go.py`: mock `run_cmd`. Test `GOOS=ios GOARCH=arm64`, release mode with `-ldflags=-s -w`.  
3. Create `tests/test_build_kotlin.py`: mock `run_cmd`. Test gradlew invocation, .kexe/.framework search.  
4. Existing `test_build_cpp.py` covers ObjC/C/C++/Swift detection — good.  

**Steps:**
```
Sub-sub-goal 4.1.1: Write test_build_rust.py (target triples, error paths)
Sub-sub-goal 4.1.2: Write test_build_go.py (cross-compile flags)
Sub-sub-goal 4.1.3: Write test_build_kotlin.py (gradlew output parsing)
Sub-sub-goal 4.1.4: Run full suite, verify 68 + new tests all pass
```

---

### Sub-goal 4.2: Add agent tests (no real LLM required)

**Plan:**
1. The agent already supports `run_agent_with_provider_plan()` mode that takes a JSON plan of pre-determined tool calls — this is testable without any API key  
2. Add `tests/test_agent.py`: test agent loop with a simple plan (build → sign → package), verify tool calls are executed in order, verify `AgentResult` has correct success/tokens/iterations  
3. Test error handling: what happens when a tool fails mid-plan  
4. Test `NoneProvider` (deterministic plan execution)  

**Steps:**
```
Sub-sub-goal 4.2.1: Create test_agent.py with plan-based tests
Sub-sub-goal 4.2.2: Test successful plan execution
Sub-sub-goal 4.2.3: Test plan with failing tool mid-execution
Sub-sub-goal 4.2.4: Test NoneProvider directly
Sub-sub-goal 4.2.5: Test agent tool registry (10 tools, schema generation)
```

---

### Sub-goal 4.3: Add coverage reporting

**Plan:**
1. Add `pytest-cov` as a dev dependency  
2. Add `[tool.coverage]` config: omit=tests/*, .pytest_cache/*  
3. Add coverage target: `python3 -m pytest tests/ --cov=src/smartapple --cov-report=term --cov-report=html`  
4. Update CI to upload coverage artifact  
5. Document coverage command in README.md  

**Steps:**
```
Sub-sub-goal 4.3.1: Add pytest-cov dev dependency
Sub-sub-goal 4.3.2: Configure tool.coverage in pyproject.toml
Sub-sub-goal 4.3.3: Add coverage step to CI workflow
Sub-sub-goal 4.3.4: Document in README.md
```

---

## Goal 5 — Documentation (3 tasks, ~1.5 hr)

**Success criteria:** README is accurate. User guide exists for all commands. CONTRIBUTING.md guides new contributors. README test count matches reality.

---

### Sub-goal 5.1: Fix README.md inaccuracies

**Plan:**
1. Line 85: `# 45 tests` → `# 68 tests` (currently says 68 on the latest, but it was 45 originally)  
2. Verify status table: update anything marked "pending" or "scaffolded" that's now verified  
3. Update language support matrix with integration test results  
4. Add "Environment Variables" section (from sub-goal 3.2)  
5. Add CI badge (from sub-goal 2.2)  

**Steps:**
```
Sub-sub-goal 5.1.1: Update test count
Sub-sub-goal 5.1.2: Update status table for verified integrations
Sub-sub-goal 5.1.3: Add environment variables section
Sub-sub-goal 5.1.4: Add CI badge
```

---

### Sub-goal 5.2: Create USER_GUIDE.md

**Plan:**
1. Write comprehensive user guide covering:
   - Installation (pip install, from source)  
   - Prerequisites (clang + lld required, SDK extraction from Mac)  
   - `init` with all 6 languages, with examples  
   - `build` with target/platform explanation  
   - `sign` with modes and when to use each  
   - `install` workflow (build → sign → package → install)  
   - `doctor` usage and auto-install  
   - `sdk` subcommands  
   - `provider` system  
   - `agent` REPL mode  
   - Troubleshooting section  
2. Link from README.md  

**Steps:**
```
Sub-sub-goal 5.2.1: Installation & prerequisites
Sub-sub-goal 5.2.2: Command reference (init, build, sign, install)
Sub-sub-goal 5.2.3: Advanced commands (doctor, sdk, provider, agent)
Sub-sub-goal 5.2.4: Troubleshooting guide
Sub-sub-goal 5.2.5: Link from README.md
```

---

### Sub-goal 5.3: Create CONTRIBUTING.md

**Plan:**
1. Document: code layout, architecture overview (link ARCHITECTURE.md), setup for development (`pip install -e ".[dev]"`)  
2. Adding a new language backend (implement Backend protocol, add to orchestrator, add template, add tests)  
3. Adding a new provider (implement BuildProvider ABC, register in registry)  
4. Testing: how to run, what requires what tools, conditional skips  
5. Code style: ruff, mypy, conventions  
6. PR process: fork, branch, test, PR against main  

**Steps:**
```
Sub-sub-goal 5.3.1: Development setup instructions
Sub-sub-goal 5.3.2: How to add a language backend
Sub-sub-goal 5.3.3: How to add a provider
Sub-sub-goal 5.3.4: Testing conventions
Sub-sub-goal 5.3.5: Code style & PR process
```

---

## Goal 6 — Packaging & Distribution (3 tasks, ~1.5 hr)

**Success criteria:** Installable via `pip install smart-apple-dev`. `smart-apple-dev --version` returns 1.0.0. CLI shell completion works. `pip install` from PyPI test instance works.

---

### Sub-goal 6.1: PyPI publishing configuration

**Plan:**
1. Update `pyproject.toml`:
   - Add `classifiers` (Development Status, Intended Audience, License, Programming Language, Operating System, Topic)  
   - Add `keywords`  
   - Add `urls` (Homepage, Repository, Documentation)  
   - Add `[project.optional-dependencies]` with `dev` extras (pytest, mypy, ruff, pytest-cov, build, twine)  
2. Verify package builds: `python3 -m build`  
3. Test install from wheel: `pip install dist/smart_apple_dev-1.0.0-py3-none-any.whl`  
4. Create `CHANGELOG.md` with v1.0.0 entries  
5. Create `.github/workflows/publish.yml` for PyPI publishing on tag push  

**Steps:**
```
Sub-sub-goal 6.1.1: Add classifiers, keywords, urls to pyproject.toml
Sub-sub-goal 6.1.2: Add dev optional dependencies
Sub-sub-goal 6.1.3: Verify build succeeds (python3 -m build)
Sub-sub-goal 6.1.4: Verify wheel install works
Sub-sub-goal 6.1.5: Create CHANGELOG.md
Sub-sub-goal 6.1.6: Create publish.yml GitHub Action
```

---

### Sub-goal 6.2: Add CLI shell completion

**Plan:**
1. Click supports shell completion natively via `@click.group`  
2. Document in USER_GUIDE.md:
   - Bash: `eval "$(_SMART_APPLE_DEV_COMPLETE=bash_source smart-apple-dev)"`  
   - Zsh: `eval "$(_SMART_APPLE_DEV_COMPLETE=zsh_source smart-apple-dev)"`  
   - Fish: `eval (env _SMART_APPLE_DEV_COMPLETE=fish_source smart-apple-dev)`  
3. This is zero-code; just documentation. Click handles the rest.  

**Steps:**
```
Sub-sub-goal 6.2.1: Document shell completion in USER_GUIDE.md
```

---

### Sub-goal 6.3: Bump version to 1.0.0

**Plan:**
1. Update `__version__` in `src/smartapple/__init__.py` from `"0.1.0"` to `"1.0.0"`  
2. Update `version` in `pyproject.toml` from `"0.1.0"` to `"1.0.0"`  
3. Update `@click.version_option(version="0.1.0")` in `cli/app.py` to `"1.0.0"`  
4. Add a test that `smart-apple-dev --version` returns `"1.0.0"`  

**Steps:**
```
Sub-sub-goal 6.3.1: Update version in __init__.py
Sub-sub-goal 6.3.2: Update version in pyproject.toml
Sub-sub-goal 6.3.3: Update version in CLI version_option
Sub-sub-goal 6.3.4: Add --version test
```

---

## Goal 7 — Feature Completion (2 tasks, ~2 hr)

**Success criteria:** `submit_for_review` works when fastlane is configured. Cloud provider interface has at least one remote provider implementation. Unspecified roadmap items are decided or deferred.

---

### Sub-goal 7.1: Complete App Store Connect submit_for_review flow

**Plan:**
1. Extend `submit_for_review()` to generate a Fastfile with `upload_to_testflight` and `submit_for_review` lanes when fastlane is available  
2. Add `--skip-build-processing-wait` flag  
3. Add `--platform` option (ios, macos, appletvos)  
4. Test with mocked fastlane invocation  
5. Update USER_GUIDE.md with App Store Connect section  

**Steps:**
```
Sub-sub-goal 7.1.1: Implement Fastfile generation with submit_for_review lane
Sub-sub-goal 7.1.2: Add --skip-build-processing-wait and --platform flags
Sub-sub-goal 7.1.3: Write tests with mocked fastlane output
Sub-sub-goal 7.1.4: Document in USER_GUIDE.md
```

---

### Sub-goal 7.2: Implement at least one cloud provider

**Plan:**
1. Choose simplest to implement: `SSHProvider` that SSHes to a Mac and runs commands remotely  
2. Implement `SSHProvider(BuildProvider)` in `src/smartapple/build/ssh_provider.py`:
   - Accepts `host`, `port`, `username`, `key_path` or `password`  
   - `is_available()` checks SSH connectivity  
   - `build()` copies project via SCP, runs build remotely, copies artifact back via SCP  
   - Uses `paramiko` (add as optional dependency)  
3. Register in `ProviderRegistry`  
4. Add `--host`, `--port`, `--username`, `--key` CLI options to `build`, `sign`, `install` commands when `--provider ssh` is selected  
5. Add basic test with mocked SSH connection  

**Steps:**
```
Sub-sub-goal 7.2.1: Add paramiko optional dependency
Sub-sub-goal 7.2.2: Implement SSHProvider class
Sub-sub-goal 7.2.3: Register SSHProvider in ProviderRegistry
Sub-sub-goal 7.2.4: Add SSH-specific CLI options
Sub-sub-goal 7.2.5: Write tests with mocked SSH
Sub-sub-goal 7.2.6: Document in USER_GUIDE.md
```

---

## Goal 8 — MAP.md Decisions (1 task, ~30 min)

**Success criteria:** All unspecified items in MAP.md are decided or explicitly deferred with rationale.

---

### Sub-goal 8.1: Resolve MAP.md open items

**Plan:**
1. **SDK extraction strategy:** Decided — implemented. Extract once on Mac, reuse everywhere.  
2. **Signing architecture:** Decided — implemented. cctools-port + ldid.  
3. **Device testing on Linux:** Decided — implemented. libimobiledevice.  
4. **App Store Connect API:** Decided — implemented. Fastlane + altool.  
5. **IDE/editor integration:** Defer to v1.1. VS Code plugin is stretch goal.  
6. **Build system abstraction:** Decided — implemented. BuildOrchestrator + per-language backends.  
7. **Distribution model:** Decided — single package on PyPI with optional language toolchains as system deps.  
8. Update MAP.md to mark all items as decided or deferred with version targets  

**Steps:**
```
Sub-sub-goal 8.1.1: Mark decided items in MAP.md
Sub-sub-goal 8.1.2: Mark deferred items with target versions
Sub-sub-goal 8.1.3: Remove "Not yet specified" section (everything is now specified or deferred)
```

---

## Execution Order (Dependency Graph)

```
Phase 1: Bugs     (Goal 1) ─────────────────────────┐
Phase 2: Infra    (Goal 2) ─────────────────────────┤
Phase 3: Quality  (Goal 3) ───── depends on 2.1 ────┤
Phase 4: Tests    (Goal 4) ───── depends on 1,3 ────┤
Phase 5: Docs     (Goal 5) ───── depends on 1-4 ────┤
Phase 6: Package  (Goal 6) ───── depends on 1-5 ────┤
Phase 7: Features (Goal 7) ───── depends on 1-4 ────┤
Phase 8: Map      (Goal 8) ───── anytime ───────────┘
```

**Recommended order:** 1 → 2 → 3 → 4 → 7 → 5 → 6 → 8  
(Features before docs, so docs describe completed features. Package last so it ships the finished product.)

---

## Estimated Total Time: ~11 hours

| Phase | Time |
|-------|------|
| Goal 1 — Bug Fixes | 0.5 hr |
| Goal 2 — Git & CI | 1.0 hr |
| Goal 3 — Code Quality | 2.0 hr |
| Goal 4 — Testing | 2.0 hr |
| Goal 5 — Documentation | 1.5 hr |
| Goal 6 — Packaging | 1.5 hr |
| Goal 7 — Feature Completion | 2.0 hr |
| Goal 8 — MAP.md Resolution | 0.5 hr |

---

## Definition of Done for v1.0.0

- [ ] Zero known bugs
- [ ] 68+ tests passing, >80% coverage
- [ ] Git repo initialized with CI (tests + lint + typecheck)
- [ ] Structured logging in all modules
- [ ] .env support for API keys
- [ ] ARCHITECTURE.md matches code
- [ ] `--json` flag on all relevant commands
- [ ] All language backends have tests
- [ ] Agent loop tested via plan mode
- [ ] README, USER_GUIDE.md, CONTRIBUTING.md complete and accurate
- [ ] Package installable via `pip install smart-apple-dev`
- [ ] `--version` returns 1.0.0
- [ ] Shell completion documented
- [ ] `submit_for_review` functional with fastlane
- [ ] At least one cloud provider (SSH) implemented
- [ ] MAP.md decisions all resolved
- [ ] CHANGELOG.md with v1.0.0 entries
- [ ] PyPI publish workflow ready