# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-09-03

### Added
- Cross-platform CLI (`smart-apple-dev`) with 11 commands: `init`, `build`, `sign`, `install`, `devices`, `doctor`, `info`, `provider`, `sdk`, `check`, `agent`
- 7 language templates: Swift, Objective-C, C++, Rust, Go, Kotlin (+ 5 experimental: Java, JavaScript, Python, C#, game engines)
- 12 build providers: local (clang+ld64.lld+SDK), SSH, GitHub Actions, AWS Mac, Azure, Codemagic, Bitrise, BuildJet, Jenkins, CircleCI, MacStadium, Nevercode
- 21 LLM providers: none, anthropic, openai, ollama, lmstudio, custom, groq, mistral, together, xai, deepseek, perplexity, copilot, gemini, opencode, nous, sambanova, cline, kilo, gateway, minimax
- Named LLM instances via `base:label` syntax (e.g. `copilot:default`, `custom:venice`) with persistent config at `~/.smart-apple-dev/llm-providers.json`
- Agentic loop with 10 tools (doctor, build, sign, install, sdk_list, read_file, write_file, run_shell, provider_list, ask_user)
- Mach-O signing via `ldid` with IPA packaging and verification
- SDK management: download, extract, and index Apple SDKs
- Firebase integration templates
- GitHub Actions CI (Python 3.11/3.12/3.13, ruff, mypy, pytest, coverage)
- PyPI publish workflow on version tags

### Fixed
- Template rendering: `module {{NAME}}` in Go, recursive `{{BUNDLE_ID}}` substitution
- ld64.lld discovery and Mach-O verification

[1.0.0]: https://github.com/smart-apple-dev/smart-apple-dev/releases/tag/v1.0.0
