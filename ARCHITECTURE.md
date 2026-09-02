# Architecture

## Module Tree

```
src/smartapple/
├── __init__.py          # version (1.0.0)
├── cli/
│   └── app.py           # Click CLI — 11 commands, 3 groups
├── core/
│   ├── config.py        # ProjectConfig, load_config (smartapple.toml)
│   └── sdk.py           # SDK index, install, extract
├── build/
│   ├── orchestrator.py  # dispatcher: language → backend
│   ├── provider.py      # 12 build providers + registry
│   ├── ssh_provider.py  # SSH provider
│   ├── cpp.py           # C/C++/ObjC (clang + ld64.lld + SDK)
│   ├── objc.py          # ObjC (clang + SDK, xtool fallback)
│   ├── swift.py         # Swift (xtool)
│   ├── rust.py          # Rust (cargo)
│   ├── go.py            # Go
│   ├── kotlin.py        # Kotlin/Native
│   ├── javascript.py    # JS/TS 🟡
│   ├── java.py          # Java 🟡
│   ├── python.py        # Python 🟡
│   ├── csharp.py        # C# 🟡
│   └── game.py          # Godot/Unity/Unreal 🟡
├── sign/                # signing + IPA (ldid/codesign)
├── device/              # device list/install (libimobiledevice)
├── store/               # App Store Connect helpers 🟡 (no CLI yet)
├── agent/
│   ├── llm.py           # 21 LLM providers + named instances
│   ├── tools.py         # 10 agent tools
│   └── loop.py          # agent loop (one-shot + REPL)
├── dev_phases/
│   └── planning.py      # planning system 🟡
└── doctor.py            # system diagnostics + auto-install
```

🟡 = present but experimental or CLI-unexposed. See README Verified Status.

## CLI Surface

Defined in `src/smartapple/cli/app.py` via `create_cli()`.

**Top-level commands:** `init`, `build`, `sign`, `install`, `devices`, `info`, `check`, `doctor`, `agent`

**Groups:**
- `sdk` → `list`, `install`, `extract`
- `provider` → `list`, `default`, `add`, `del`, `list-instances`

No `store` group yet — `store/` helpers are Python-only.

## Data Flow

```
init  →  smartapple.toml + template
build →  orchestrator → provider → backend (clang/xtool/cargo/…) → build/<target>/
sign  →  ldid/codesign → .app → package_ipa() → .ipa
install → ideviceinstaller / ios-deploy → device
agent →  llm.py (21 providers) ↔ loop.py ↔ tools.py → build/sign/…
doctor →  check_tool() + SDK index → report + optional auto-install
```

## Key Decisions

- **No Xcode required** — clang + ld64.lld + SDK extraction; verified Mach-O on Linux.
- **ldid from source** — ProcursusTeam/ldid built on Linux for ad-hoc signing.
- **OpenAI-compatible base** — 8 new cloud/local providers share `OpenAICompatibleProvider`, cutting ~1K lines.
- **Named instances** — `base:label` with `~/.smart-apple-dev/llm-providers.json`, `${ENV_VAR}` for keys.
- **Deterministic testing** — `NoneProvider` (plan-based) for loop tests; no API keys needed.
- **Click for CLI** — cross-platform, no Go/Rust dep.
