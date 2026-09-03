# smart-apple-dev v1.0 Public Release Plan

**Updated:** post-implementation audit
**Current state:** 108/110 tests pass on Linux; CLI runs end-to-end with `NoneProvider`; build pipeline works for ObjC/macOS with downloaded MacOSX SDK
**Strategy:** open-source MIT release, dual monetization (open-core + cloud)

---

## Audit Snapshot

| Area | Status | Notes |
|------|--------|-------|
| CLI | ✅ 11 commands | init, build, sign, install, devices, doctor, info, provider, sdk, check, agent |
| Languages | ✅ 7 templates | swift, objc, cpp, rust, go, kotlin + 5 experimental (java, js, python, csharp, game) |
| Build providers | ✅ 12 | local, ssh, github-actions, aws-mac, azure, codemagic, bitrise, buildjet, jenkins, circleci, macstadium, nevercode |
| LLM providers | ✅ 21 | none, anthropic, openai, ollama, lmstudio, custom, groq, mistral, together, xai, deepseek, perplexity, copilot, gemini, opencode, nous, sambanova, cline, kilo, gateway, minimax |
| Named instances | ✅ Working | `base:label` syntax, persistent config, 7 built-in examples |
| Tests | ✅ 108 pass | 2 pre-existing failures (version mismatch, macOS-only build) |
| Lint | ✅ 0 errors | ruff passes |
| Type check | ✅ 0 errors | mypy passes |
| CI | ✅ Configured | GitHub Actions, Python 3.11/3.12/3.13, lint+type+test |
| PyPI publish | ✅ Configured | via `gh-action-pypi-publish` on tag |
| License | ✅ MIT | full text in `LICENSE` |
| GitHub remote | ✅ set | `realstreetsmartnyc/smart-apple-dev` |
| SECURITY.md | ✅ present | vulnerability disclosure policy |
| CODE_OF_CONDUCT | ✅ present | Contributor Covenant v2.1 |
| Issue templates | ✅ present | bug/feature/question + PR template |
| Screenshot/GIF | ✅ present | `docs/banner.svg` + `docs/banner-android.svg` |
| Landing page | ✅ present | MkDocs site at `realstreetsmartnyc.github.io/smart-apple-dev` |
| Version sync | ✅ 1.0.0 | aligned across pyproject.toml, __init__.py, cli/app.py |
| Real device install | ⚠️  Limited | iOS: libimobiledevice on Linux; Android: adb |
| Android build target | ✅ | Kotlin template → APK via `./gradlew assembleDebug` |
| Android device install | ✅ | adb wrapper, fake-shim in `verify-android.sh` |
| Verify scripts | ✅ | `verify/verify.sh` + `verify/verify-android.sh` |
| Example projects | ✅ | `examples/hello-objc/` + `examples/hello-kotlin/` |
| Release workflow | ✅ | `.github/workflows/release.yml` (tag-triggered) |
| Docs deploy workflow | ✅ | `.github/workflows/docs.yml` (GitHub Pages) |

---

## Goal: Public v1.0.0 Release on GitHub + PyPI

### Phase A: Repository Hygiene (Day 1, ~2 hours)
**Goal:** make the repo public-ready

- [ ] **A1.** Create `LICENSE` (MIT, full text)
- [ ] **A2.** Add `CODE_OF_CONDUCT.md` (Contributor Covenant v2.1)
- [ ] **A3.** Add `SECURITY.md` (vulnerability disclosure policy, supported versions)
- [ ] **A4.** Add `.github/ISSUE_TEMPLATE/bug_report.md`
- [ ] **A5.** Add `.github/ISSUE_TEMPLATE/feature_request.md`
- [ ] **A6.** Add `.github/ISSUE_TEMPLATE/question.md`
- [ ] **A7.** Add `.github/PULL_REQUEST_TEMPLATE.md`
- [ ] **A8.** Add `CHANGELOG.md` (initial v1.0.0 entry)
- [ ] **A9.** Fix version drift: align `src/smartapple/__init__.py`, `src/smartapple/cli/app.py`, `src/smartapple/core/config.py` to 1.0.0
- [ ] **A10.** Set up git remote: `git remote add origin git@github.com:smart-apple-dev/smart-apple-dev.git`
- [ ] **A11.** Push master → main rename, configure branch protection
- [ ] **A12.** Update pyproject.toml `authors` to a real name/email
- [ ] **A13.** Decide on `Repository` URL — confirm org/handle

### Phase B: Truthful README (Day 1, ~2 hours)
**Goal:** every claim has evidence

- [ ] **B1.** Rewrite README "Status" table — split into ✅ verified / 🟡 partial / ❌ not implemented
- [ ] **B2.** Mark all "experimental" language backends (java, js, python, csharp, game) as 🟡 in README
- [ ] **B3.** Remove the App Store Connect "implemented" claim if there's no `store` CLI group
- [ ] **B4.** Add a "Verified On" section: Linux 5.x Ubuntu 22.04, Python 3.11/3.12/3.13, MacOSX SDK 11.3
- [ ] **B5.** Add a "Known Limitations" section: device install requires macOS or libimobiledevice, real cert signing needs Apple Developer ID
- [ ] **B6.** Add a "Quickstart" block: 3-line install + hello world
- [ ] **B7.** Add a "Screenshots" section placeholder (or inline terminal GIF)
- [ ] **B8.** Add a "Why smart-apple-dev?" section comparing to fastlane, xcodebuild, osxcross

### Phase C: Working Demo (Day 1-2, ~4 hours)
**Goal:** an "impressive in 60 seconds" reproduction

- [ ] **C1.** End-to-end test script: `scripts/demo.sh` that does init → build → sign → IPA in <60s
- [ ] **C2.** Record terminal GIF of the demo (asciinema or ttyrec)
- [ ] **C3.** Embed the GIF in README + a `docs/demo.md`
- [ ] **C4.** Create `examples/hello-objc/` with a real tested project
- [ ] **C5.** Add a "Compare to other tools" page
- [ ] **C6.** Make the install one-liner work: `pip install smart-apple-dev`

### Phase D: PyPI Release (Day 2, ~1 hour)
**Goal:** installable via `pip install smart-apple-dev`

- [ ] **D1.** Create PyPI account & API token
- [ ] **D2.** Add PYPI_API_TOKEN to GitHub repo secrets
- [ ] **D3.** Tag v1.0.0: `git tag -a v1.0.0 -m "Initial public release"`
- [ ] **D4.** Push tag → triggers CI publish workflow
- [ ] **D5.** Verify install: `pip install smart-apple-dev` in a fresh venv
- [ ] **D6.** Test the installed CLI: `smart-apple-dev --version`, `smart-apple-dev doctor`
- [ ] **D7.** Add "Get it on PyPI" badge to README

### Phase E: GitHub Public Release (Day 2, ~1 hour)
**Goal:** discoverable from GitHub

- [ ] **E1.** Switch repo from private → public
- [ ] **E2.** Write GitHub Release notes for v1.0.0 (use the CHANGELOG entry)
- [ ] **E3.** Attach demo GIF to release
- [ ] **E4.** Enable GitHub Discussions
- [ ] **E5.** Pin a "Welcome" discussion with quickstart
- [ ] **E6.** Add repo topics: ios, macos, swift, xcode, cross-platform, cli, mobile-development
- [ ] **E7.** Add repo description and homepage URL
- [ ] **E8.** Configure social preview image (1280x640)

### Phase F: Documentation Site (Day 2-3, ~6 hours)
**Goal:** searchable, beautiful docs

Options (pick one):
  - **F1a.** GitHub Pages + MkDocs Material (free, easy)
  - **F1b.** Read the Docs (free, standard)
  - **F1c.** Mintlify (paid, slickest UI)

Recommendation: F1a (MkDocs Material) for v1.0, migrate later if needed.

- [ ] **F1.** Add `mkdocs.yml` + `docs/` directory
- [ ] **F2.** Pages: index, installation, quickstart, providers, llm-providers, templates, ci-integration, faq
- [ ] **F3.** Auto-generate API reference from docstrings
- [ ] **F4.** Set up custom domain (optional)
- [ ] **F5.** Enable Algolia DocSearch (free for OSS)

### Phase G: Community Signal (Day 3, ~3 hours)
**Goal:** first impressions matter

- [ ] **G1.** Post to r/iOSProgramming, r/Python, r/swift
- [ ] **G2.** Tweet thread (tag @SwiftLang, @pyplang)
- [ ] **G3.** Post on Hacker News "Show HN"
- [ ] **G4.** Post on Product Hunt (pre-launch page first)
- [ ] **G5.** Submit to awesome-swift, awesome-ios lists
- [ ] **G6.** Write a blog post comparing it to fastlane
- [ ] **G7.** Add a "Star History" badge to README

### Phase H: Monetization (Day 3-7, ~10 hours)
**Goal:** paths to revenue, all opt-in

#### H1. Open-source tier (free, MIT)
- Core CLI
- All 21 LLM providers (BYOK or local)
- All 12 build providers
- Self-hosted only

#### H2. Open-core: optional paid features
- **H2a.** Cloud-hosted build runners (managed Mac mini pool)
  - Pricing: $0.10/build minute, free tier 100 min/month
  - Implementation: thin layer over `SSHProvider` + autoscaling pool
- **H2b.** Premium LLM gateway: 1-credit pricing across all 21 providers
  - Implementation: LLM proxy at `api.smart-apple-dev.com`, returns normalized OpenAI-format
  - Pricing: $0.001/1k tokens, $5 free credit at signup
- **H2c.** Team features: shared `llm-providers.json`, audit log, RBAC
  - Implementation: paid SaaS at `app.smart-apple-dev.com`
- **H2d.** Priority CI: faster Mac runners, private queue
  - Implementation: tier gating on `MacStadiumProvider` / `BuildJetProvider`

#### H3. Service offerings
- **H3a.** Consulting: help teams migrate from fastlane / Jenkins (book a call)
- **H3b.** Custom templates: commissioned templates for niche stacks
- **H3c.** Enterprise support: 24h SLA, custom provider integrations

#### H4. Sponsorship
- **H4a.** GitHub Sponsors setup (sponsor tiers: $10/$50/$500/mo)
- **H4b.** Open Collective for transparent finances
- **H4c.** Polar.sh for paid feature bounties

#### H5. Affiliate revenue (low-effort)
- **H5a.** Refer MacStadium / BuildJet / Codemagic → 10-20% referral fee
- **H5b.** Refer cloud LLM providers (OpenRouter, Together) → 5-10% credit
- **H5c.** Disclosure: "links marked * are affiliate links"

---

## Phased Timeline

| Day | Focus | Exit Criteria |
|-----|-------|---------------|
| 1  | A + B | Repo clean, README truthful, demo works |
| 2  | C + D | pip install works, PyPI live |
| 3  | E + G | Public on GitHub, social posts live |
| 4-5 | F | Docs site live |
| 6-7 | H scaffolding | Sponsor links, pricing page drafted |
| 8-14 | H2a (cloud build) | First paying user |
| 15-30 | Iterate | Bug fixes, more providers, more templates |

---

## Risk & Mitigations

| Risk | Mitigation |
|------|------------|
| Build on macOS-only features (xcrun) | Already mitigated: clang+lld+SDK on Linux works |
| User confusion about LLM provider model names | KNOWN_MODELS + `provider list --show-models` |
| Vendor lock-in via paid features | Premium is opt-in; free tier covers 90% of use cases |
| Apple ToS violations | All signing uses user's own certs; we don't host certs |
| Maintenance burden | Keep providers modular; document "how to add a provider" |
| Negative HN reception | Pre-test with friendly users; have demo GIF ready |

---

## Success Metrics (90 days)

- [ ] 1,000+ GitHub stars
- [ ] 5,000+ PyPI downloads/month
- [ ] 100+ Discord / Discussions members
- [ ] 5+ external contributors
- [ ] 10+ paying customers ($100+/mo total)
- [ ] <24h response time on issues

---

## Decision Log (rationale)

**Why MIT, not GPL?** Maximize adoption; monetize on service, not license.

**Why PyPI, not Homebrew first?** Linux/Windows users are the primary audience; PyPI covers them. Add Homebrew tap at 1k stars.

**Why a paid cloud tier?** Self-hosted works but Mac runners are expensive; managed service is real value.

**Why 21 LLM providers, not just one?** Each user has different cost/quality/privacy needs; the tool should fit their stack, not the other way around.

**Why named instances (`base:label`)?** Real users have multiple GitHub accounts, multiple API keys, multiple regions. The `base:label` syntax matches how people actually work.

---

## Immediate Next Actions (today)

1. Create LICENSE, CHANGELOG, SECURITY, CODE_OF_CONDUCT
2. Fix version drift (3 files → 1.0.0)
3. Rewrite README status table to match test evidence
4. Run the demo end-to-end on a fresh machine
5. Record the GIF
6. Push to GitHub (public)
7. Tag v1.0.0 → triggers PyPI publish
8. Post on HN
