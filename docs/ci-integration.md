# CI integration

`smart-apple-dev` runs on every push to `main` via
[`.github/workflows/ci.yml`][ci-yml]. The workflow is intentionally simple:

[ci-yml]: https://github.com/realstreetsmartnyc/smart-apple-dev/blob/main/.github/workflows/ci.yml

## Jobs

### `test` — runs on Ubuntu for every supported Python

```yaml
- ubuntu-latest
- Python 3.11 / 3.12 / 3.13
- apt: clang lld make tar curl git cmake pkg-config
- pip install -e ".[dev]"
- ruff check
- mypy src/
- pytest tests/ --cov
- codecov upload
```

### `android` — Kotlin template APK build

```yaml
- ubuntu-latest
- JDK 17 (Temurin)
- Android cmdline-tools 11076708
- yes | sdkmanager --licenses
- sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0"
- Gradle cache
- ./gradlew assembleDebug in templates/kotlin/
- Verify: APK exists, is a valid ZIP, contains AndroidManifest.xml
- pytest tests/test_android_target.py -v
```

### `publish` — PyPI on tag

Triggered by `git tag vX.Y.Z && git push --tags`. Builds the wheel +
sdist and publishes via `pypa/gh-action-pypi-publish@release/v1` using
`secrets.PYPI_API_TOKEN`.

## Using smart-apple-dev in your own CI

```yaml
- uses: actions/checkout@v4
- uses: actions/setup-python@v5
  with: { python-version: "3.12" }
- run: pip install smart-apple-dev
- run: smart-apple-dev build --target macos
  env: { MACOSX_SDK_URL: ${{ secrets.MACOSX_SDK_URL }} }
```

## Self-hosted runners

`smart-apple-dev` is provider-agnostic — point it at any macOS box
(your own Mac mini, a hosted Mac from MacStadium, etc.) with the
`--provider ssh` flag, or use any of the 12 cloud providers in
[Build providers](providers.md).
