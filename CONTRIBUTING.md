# Contributing to smart-apple-dev

Thanks for your interest in improving smart-apple-dev! This guide covers how to set up a development environment, run tests, and submit changes.

## Development Setup

### Prerequisites

- Python 3.11 or later
- Linux, macOS, or WSL2 on Windows
- Git

### Install

```bash
git clone https://github.com/smart-apple-dev/smart-apple-dev
cd smart-apple-dev
pip install -e ".[dev]"
```

This installs smart-apple-dev in development mode with all testing and linting tools.

### Verify Installation

```bash
smart-apple-dev --version
smart-apple-dev doctor
```

## Project Structure

```
smart-apple-dev/
├── src/smartapple/              # Source code
│   ├── __init__.py              # Package version
│   ├── cli/                     # CLI commands
│   │   └── app.py               # Click-based CLI (12 commands)
│   ├── core/                    # Core utilities
│   │   ├── config.py            # Project config (smartapple.toml)
│   │   └── sdk.py               # SDK management
│   ├── build/                   # Build backends
│   │   ├── orchestrator.py      # Build dispatcher
│   │   ├── provider.py          # Provider system (local, SSH)
│   │   ├── swift.py             # Swift backend (xtool)
│   │   ├── cpp.py               # C/C++/ObjC backend (clang + LLD)
│   │   ├── rust.py              # Rust backend (cargo + cross-rs)
│   │   ├── go.py                # Go backend (native cross-compile)
│   │   ├── kotlin.py            # Kotlin/Native backend (gradle)
│   │   └── ssh_provider.py      # SSH provider (remote Mac)
│   ├── sign/                    # Signing + IPA packaging
│   │   └── __init__.py          # Signer, IPA packaging, provisioning
│   ├── device/                  # iOS device management
│   │   └── __init__.py          # libimobiledevice wrapper
│   ├── store/                   # App Store Connect
│   │   └── __init__.py          # Fastlane + altool upload
│   ├── agent/                   # LLM agent
│   │   ├── __init__.py          # Agent module
│   │   ├── llm.py               # LLM provider abstraction
│   │   ├── tools.py             # Agent tool registry
│   │   └── loop.py              # ReAct-style agent loop
│   └── doctor.py                # Toolchain diagnostics
├── templates/                   # Project templates
│   ├── swift/                   # Swift template
│   ├── objc/                    # Objective-C template
│   ├── cpp/                     # C++ template
│   ├── rust/                    # Rust template
│   ├── go/                      # Go template
│   └── kotlin/                  # Kotlin/Native template
├── tests/                       # Test suite
├── .github/workflows/ci.yml     # CI pipeline
├── pyproject.toml               # Build configuration
├── .env.example                 # Environment variable template
├── .gitignore                   # Git ignore rules
├── README.md                    # User-facing readme
├── USER_GUIDE.md                # Full command reference
├── ARCHITECTURE.md              # Design document
├── MAP.md                       # Roadmap and decisions
├── CONTRIBUTING.md              # This file
└── PUBLISH_PLAN.md              # Publish readiness plan
```

## Code Style

### Linting

```bash
ruff check src/ tests/
```

### Type Checking

```bash
mypy src/
```

### Formatting

smart-apple-dev uses `ruff` for both linting and formatting. Run:

```bash
ruff format src/ tests/
```

### Conventions

- **Line length**: 100 characters (enforced by ruff)
- **Type annotations**: All public functions and methods should have type hints
- **Docstrings**: Use Google-style docstrings for public APIs
- **Imports**: `ruff` will auto-sort imports (isort)
- **Logging**: Use `logging` module (via `core/logger.py`), not `print()`

## Testing

### Run All Tests

```bash
pytest tests/ -v
```

### Run with Coverage

```bash
pytest tests/ -v --cov=src/smartapple --cov-report=term-missing
```

### Run Specific Tests

```bash
# Single test file
pytest tests/test_config.py -v

# Single test function
pytest tests/test_config.py::test_default_config -v

# Integration tests (requires clang + LLD + SDK)
pytest tests/test_build_cpp.py -v
```

### Test Conventions

- Tests are organized by module: `test_config.py`, `test_sdk.py`, `test_orchestrator.py`, etc.
- Integration tests that require system tools (clang, LLD, SDK, ldid) are marked with `pytest.mark.skipif` and skip gracefully when tools are missing
- Mock external commands (like `run_cmd`) to test backends without actual compilation
- Use `conftest.py` to set up `sys.path` for importing `smartapple` from `src/`

## Adding a New Language Backend

1. Create a backend class in `src/smartapple/build/<language>.py` that inherits from `Backend` (if it exists) or implements the `build()` interface
2. Add the language to `BuildOrchestrator._get_backend()` mapping
3. Add the language to `BuildOrchestrator._create_backend()` backends dict
4. Add the language to `BuildOrchestrator._backend_checks()` tool checks
5. Add a template directory under `templates/<language>/` with at minimum:
   - `smartapple.toml` (config template with `{{NAME}}` and `{{BUNDLE_ID}}` placeholders)
   - Language-specific source file (e.g., `main.py`, `main.c`, `main.go`)
   - Build system file (e.g., `Makefile`, `CMakeLists.txt`, `Cargo.toml`, `go.mod`, `build.gradle.kts`)
6. Add tests in `tests/test_build_<language>.py` that mock `run_cmd` to test the backend logic without actually compiling
7. Add the language to `CLI` `--lang` choice list in `cli/app.py`
8. Update README.md and USER_GUIDE.md

## Adding a New Provider

1. Create a provider class in `src/smartapple/build/<provider_name>.py` that inherits from `BuildProvider`
2. Implement the abstract methods: `capabilities()`, `is_available()`, `build()`
3. Register the provider in `ProviderRegistry.__init__()` by calling `self.register(YourProvider())`
4. Add CLI options for the provider in `cli/app.py` (e.g., `--provider ssh`)
5. Add tests in `tests/test_provider.py` that mock the provider's external dependencies
6. Update USER_GUIDE.md with the new provider

## Submitting Changes

1. **Fork** the repository and create a feature branch from `main`
2. **Write tests** for any new functionality or bug fix
3. **Run the full test suite** and ensure all tests pass
4. **Run linting and type checking** and fix any issues
5. **Commit** with a clear message:
   ```
   <type>(<scope>): <description>

   <body>
   <footer>
   ```
   Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`
6. **Push** your branch and open a pull request against `main`

## Reporting Issues

Use the GitHub issue tracker. Include:

- **smart-apple-dev version** (`smart-apple-dev --version`)
- **OS** (Linux/Windows/macOS)
- **Python version** (`python3 --version`)
- **Reproducible steps** (what you did, what you expected, what happened)
- **Output** (any error messages or logs)
- **Environment variables** (if relevant, redact secrets)

## License

By contributing, you agree that your contributions will be licensed under the MIT license.