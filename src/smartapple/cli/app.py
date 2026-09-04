"""smart-apple-dev CLI application."""

import json
import os
import re
import sys
from pathlib import Path

try:
    import click
except ImportError:
    click = None

from .. import ui
from ..core.config import ProjectConfig, load_config, find_project_root, ensure_dirs, get_platform
from ..core.sdk import list_installed_sdks, install_sdk, SdkError
from ..build.orchestrator import BuildOrchestrator
from ..sign import sign_artifact
from ..device import list_devices, install_ipa


def _get_click():
    if click is None:
        print("Error: click is required. Install with: pip install click")
        sys.exit(1)

    return click
def create_cli():


    """Create the CLI application."""
    click = _get_click()

    @click.group()
    @click.version_option(version="1.0.0")
    def cli():
        """smart-apple-dev: Cross-platform iOS/macOS development toolchain."""
        pass

    @cli.command()
    @click.argument("name")
    @click.option("--lang", default="swift",
                  type=click.Choice(["swift", "objc", "cpp", "rust", "go", "kotlin"]),
                  help="Programming language")
    @click.option("--bundle-id", default=None, help="App bundle identifier")
    def init(name, lang, bundle_id):
        """Create a new smart-apple-dev project."""
        project_dir = Path.cwd() / name
        if project_dir.exists():
            ui.error(f"{name} already exists at {project_dir}")
            sys.exit(1)
        project_dir.mkdir(parents=True)

        # Write config
        config_path = project_dir / "smartapple.toml"
        bundle = bundle_id or f"com.example.{name}"
        config_content = f"""[project]
name = "{name}"
language = "{lang}"
bundle_id = "{bundle}"
version = "0.1.0"
build_system = "swiftpm"
min_os = "15.0"
target = "ios"
"""
        config_path.write_text(config_content)

        # Create template based on language
        template_dir = Path(__file__).parent.parent.parent.parent / "templates" / lang
        if not template_dir.exists():
            ui.error(f"no template found for language '{lang}'")
            sys.exit(1)

        # Pre-flight: warn if no Apple SDK is installed and target is Apple.
        # We do not block — the user may have other plans — but make it loud
        # so a fresh box doesn't silently produce a project that won't build.
        try:
            from ..core.sdk import list_installed_sdks
            sdks = list_installed_sdks()
        except Exception:
            sdks = []
        if not sdks and lang in ("objc", "cpp", "rust", "go", "swift", "kotlin"):
            ui.warning("No Apple SDK installed.")
            ui.hint(
                f"smart-apple-dev will scaffold the project, but a build will fail "
                f"until an SDK is installed. Run:\n"
                f"  smart-apple-dev sdk install macosx 14.0\n"
                f"or place a MacOSX*.sdk.tar.xz in {Path.home() / '.smart-apple-dev' / 'sdk'}/"
            )
            # Non-interactive: just continue. The build will fail with a clear
            # error pointing to sdk install. We could add `--strict-sdk`
            # to abort here if desired.

        # Template variables. Provide both Jinja style {{ NAME }} and
        # placeholder style {{NAME}} for compatibility.
        template_vars = {
            "NAME": name,
            "BUNDLE_ID": bundle,
            "LANGUAGE": lang,
            "TARGET": "macos",  # default; user can edit smartapple.toml
        }

        # Extended vars: many templates reference build/CI vars. Provide
        # reasonable defaults; users can edit smartapple.toml after init.
        template_vars.update({
            "ARCH": "arm64",
            "PLATFORM": "macos",
            "PROFILE": "debug",
            "OPT_LEVEL": "0",
            "LTO": "false",
            "CODEGEN_UNITS": "auto",
            "GOOS": "darwin",
            "GOARCH": "arm64",
            "RELEASE": "false",
            "TEAM_ID": "",
            "PROVISIONING_PROFILE": "",
            "MIN_OS": "15.0",
            "CI_PROVIDER": "github-actions",
            "BUILD_NUMBER": "1",
            "VERSION_CODE": "1",
            "IOS_DEVICE_TARGET": "",
            "IOS_SDK": "",
            "TARGET_PLATFORM": "",
            "DEVELOPMENT": "false",
            "RP_ACTIVE": "",
        })

        try:
            from jinja2 import Environment, ChainableUndefined
            env = Environment(undefined=ChainableUndefined, keep_trailing_newline=True)

            def render(text: str) -> str:
                t = env.from_string(text)
                return t.render(**template_vars)

        except ImportError:
            # Fallback: simple {{KEY}} replacement (no conditionals).
            def render(text: str) -> str:
                for k, v in template_vars.items():
                    text = text.replace("{{" + k + "}}", str(v))
                return text

        def copy_template(src: Path, dst: Path) -> None:
            if src.is_file():
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(render(src.read_text()))
            elif src.is_dir():
                dst.mkdir(parents=True, exist_ok=True)
                for child in src.iterdir():
                    copy_template(child, dst / child.name)

        with ui.spinner(f"Scaffolding {name} ({lang}) from template"):
            for item in template_dir.iterdir():
                copy_template(item, project_dir / item.name)

        ui.success(f"Created {name} ({lang}) at {project_dir}")
        ui.info(f"Config: {config_path}")
        ui.summary([
            ("Project", str(project_dir)),
            ("Language", lang),
            ("Bundle ID", bundle),
            ("Next", f"cd {name} && smart-apple-dev build"),
        ])

    @cli.command()
    @click.option("--target", default="ios",
                  type=click.Choice(["ios", "ios-simulator", "macos", "catalyst", "android"]),
                  help="Build target")
    @click.option("--release", is_flag=True, help="Release build")
    @click.option("--provider", default=None,
                  help="Build provider (default: auto-detect)")
    def build(target, release, provider):
        """Build the current project."""
        root = find_project_root()
        if root is None:
            ui.error("No smartapple.toml found. Run 'smart-apple-dev init' first.")
            sys.exit(1)

        config = load_config(root)
        from ..build.provider import get_provider
        prov = get_provider(provider)
        available, reason = prov.is_available()
        if not available:
            ui.error(f"Provider '{prov.name}' not available: {reason}")
            sys.exit(1)

        task_label = f"Building {config.name} for {target}" + (" (release)" if release else "")
        with ui.spinner(f"{task_label} via {prov.name}"):
            result = prov.build(root, config, target=target, release=release)

        if result.success:
            ui.success(f"Build succeeded via {prov.name} ({result.metadata.get('language', '')})")
            rows = [
                ("Build", "succeeded"),
                ("Provider", prov.name),
                ("Language", str(result.metadata.get("language", ""))),
                ("Target", target),
            ]
            if result.artifact:
                rows.append(("Artifact", str(result.artifact)))
            if result.duration_seconds:
                rows.append(("Duration", f"{result.duration_seconds:.1f}s"))
            ui.summary(rows)
        else:
            ui.error(f"Build failed via {prov.name}")
            for err in result.errors:
                ui.error(f"  {err}")
                if "ANDROID" in err or "SDK" in err:
                    ui.hint("Set ANDROID_HOME / ANDROID_SDK_ROOT, or run: smart-apple-dev doctor --install")
                elif "JDK" in err:
                    ui.hint("Install JDK 17+: sudo apt install openjdk-17-jdk")
                elif "licenses" in err.lower():
                    ui.hint("Accept Android SDK licenses: yes | sdkmanager --licenses")
            if result.output:
                ui.info(f"Last output: {result.output.strip().splitlines()[-1][:200]}")
            sys.exit(1)

    @cli.command()
    @click.option("--mode", default="ad-hoc",
                  type=click.Choice(["ad-hoc", "identity", "skip"]),
                  help="Signing mode: ad-hoc (no cert), identity (real cert), skip (no signing)")
    @click.option("--identity", default=None,
                  help="Apple developer identity (required for mode=identity)")
    @click.option("--profile", "-p", default=None, type=click.Path(exists=True),
                  help="Path to .mobileprovision (iOS only)")
    @click.option("--entitlements", "-E", default=None, type=click.Path(exists=True),
                  help="Path to entitlements.plist")
    @click.option("--ipa", "-i", "to_ipa", is_flag=True,
                  help="After signing, package the .app into a .ipa (Apple targets only)")
    @click.option("--target", "-t", default=None,
                  type=click.Choice(["ios", "ios-simulator", "macos", "catalyst", "android"]),
                  help="Build target (default: from smartapple.toml)")
    def sign(mode, identity, profile, entitlements, to_ipa, target):
        """Sign the built app (and optionally package it as an .ipa)."""
        from ..sign import package_ipa
        root = find_project_root()
        if root is None:
            print("Error: No smartapple.toml found.")
            sys.exit(1)

        config = load_config(root)
        target = target or config.target or "ios"
        orchestrator = BuildOrchestrator(root)
        result = orchestrator.build(config, target=target)

        if not result.success or result.artifact is None:
            print("Error: Build failed, cannot sign.")
            sys.exit(1)

        profile_path = Path(profile) if profile else None
        entitlements_path = Path(entitlements) if entitlements else None

        sign_result = sign_artifact(
            result.artifact, config,
            identity=identity,
            provisioning_profile=profile_path,
            entitlements=entitlements_path,
            mode=mode,
        )

        for w in sign_result.warnings:
            ui.warning(w)

        if not sign_result.success:
            ui.error("Signing failed")
            for err in sign_result.errors:
                ui.error(f"  {err}")
            sys.exit(1)

        if sign_result.signed:
            ui.success(f"Signed: {sign_result.artifact_path}")
        else:
            ui.warning(f"Build OK but not signed: {sign_result.artifact_path}")
            for w in sign_result.warnings:
                ui.warning(f"  {w}")

        if to_ipa:
            with ui.spinner("Packaging .ipa"):
                ipa_path = package_ipa(sign_result.artifact_path)
            ui.success(f"IPA: {ipa_path} ({ipa_path.stat().st_size:,} bytes)")

    @cli.command()
    @click.option("--artifact", "-a", "artifact_path", default=None,
                  type=click.Path(exists=True),
                  help="Path to the .app or .pkg to notarize (default: build/<target>/<name>.app)")
    @click.option("--identity", "-i", default=None,
                  help="Keychain profile name (for xcrun notarytool)")
    @click.option("--remote", "remote_host", default=None,
                  help="SSH user@host to run notarization on a remote Mac")
    @click.option("--bundle-id", default=None,
                  help="com.example.app identifier (for stapling)")
    def notarize(artifact_path, identity, remote_host, bundle_id):
        """Notarize a macOS .app for distribution outside the App Store.

        On macOS: uses xcrun notarytool + stapler.
        On Linux/Windows: requires --remote to SSH into a Mac.

        The credential store is the same as Apple's docs recommend:
        `xcrun notarytool store-credentials <name>`. The keychain profile
        name is passed via --identity.
        """
        from ..notarize import notarize_app
        root = find_project_root()
        if root is None:
            ui.error("No smartapple.toml found. Run `smart-apple-dev init` first.")
            sys.exit(1)
        config = load_config(root)

        # Default artifact path
        if artifact_path is None:
            target = config.target or "macos"
            name = config.name
            candidate = root / "build" / target / f"{name}.app"
            if candidate.exists():
                artifact_path = str(candidate)
            else:
                ui.error(f"Could not find {candidate}; pass --artifact explicitly.")
                sys.exit(1)

        result = notarize_app(
            artifact_path,
            identity=identity,
            remote_host=remote_host,
            bundle_id=bundle_id or config.bundle_id,
        )
        if not result.success:
            ui.error("Notarization failed")
            for err in result.errors:
                ui.error(f"  {err}")
            sys.exit(1)
        for w in result.warnings:
            ui.warning(w)
        ui.success(f"Notarized: {result.artifact_path}")
        if result.ticket_path:
            ui.info(f"Stapled ticket: {result.ticket_path}")

    @cli.command()
    @click.argument("name")
    @click.option("--lang", default="objc",
                  type=click.Choice(["swift", "objc", "cpp", "rust", "go", "kotlin"]),
                  help="Project language (default: objc)")
    @click.option("--bundle-id", default=None,
                  help="App bundle identifier (default: com.example.<name>)")
    @click.option("--target", default=None,
                  type=click.Choice(["ios", "ios-simulator", "macos", "android"]),
                  help="Build target (default: from smartapple.toml after init)")
    def new(name, lang, bundle_id, target):
        """Scaffold a new project AND run an initial build to confirm the toolchain.

        Equivalent to `init <name> --lang <lang>` followed by `build` and
        `sign --mode ad-hoc --ipa` for Apple targets, or `build` for
        Android. Exits non-zero if the initial build fails so CI can
        detect a broken toolchain immediately.
        """
        runner = _get_click()
        # Delegate to init first
        ctx = runner.Context(  # type: ignore[attr-defined]
            cli, info_name="smart-apple-dev", resilient_parsing=True,
        )
        try:
            init_cmd = cli.commands["init"]
            ctx.invoke(init_cmd, name=name, lang=lang, bundle_id=bundle_id)
        except SystemExit as e:
            if e.code != 0:
                raise

        project_dir = Path.cwd() / name
        if not project_dir.exists():
            ui.error(f"init did not create {project_dir}")
            sys.exit(1)
        os.chdir(project_dir)

        # Override target if provided
        if target is not None:
            cfg_path = project_dir / "smartapple.toml"
            text = cfg_path.read_text()
            import re as _re
            text = _re.sub(r'target = "[^"]+"', f'target = "{target}"', text)
            cfg_path.write_text(text)

        # Initial build
        try:
            build_cmd = cli.commands["build"]
            ctx.invoke(build_cmd, target=target) if target else ctx.invoke(build_cmd)
        except SystemExit as e:
            if e.code != 0:
                ui.hint("Run `smart-apple-dev doctor` to debug toolchain issues.")
                raise

        # If Apple target and build succeeded, also do ad-hoc sign + ipa
        if target is None or target in ("macos", "ios", "ios-simulator"):
            try:
                sign_cmd = cli.commands["sign"]
                ctx.invoke(sign_cmd, mode="ad-hoc", to_ipa=True, target=target or "macos")
            except SystemExit:
                # Non-fatal: build was OK, sign may have its own issues
                pass

        ui.summary([
            ("Project", str(project_dir)),
            ("Language", lang),
            ("Next: device install", f"smart-apple-dev install (iOS, requires USB)"),
            ("Next: open in editor", f"cd {project_dir} && code ."),
        ])

    @cli.group()
    def xtool():
        """Manage the xtool environment (Swift for Linux + xtool)."""
        pass

    @xtool.command(name="status")
    @click.option("--json", "as_json", is_flag=True,
                  help="Output machine-readable JSON")
    def xtool_status(as_json):
        """Report the current xtool environment state."""
        from ..xtool_env import xtool_status as _status
        s = _status()
        if as_json:
            import json as _json
            print(_json.dumps(s.to_dict(), indent=2))
            return
        rows = [
            ("Platform", s.platform),
            ("Swift installed", "yes" if s.swift_installed else "no"),
            ("Swift version", s.swift_version or "-"),
            ("Swift path", s.swift_path or "-"),
            ("xtool cloned", "yes" if s.xtool_cloned else "no"),
            ("xtool built", "yes" if s.xtool_built else "no"),
            ("xtool path", s.xtool_path or "-"),
            ("On PATH", "yes" if s.on_path else "no"),
        ]
        ui.summary(rows)
        if s.notes:
            print()
            for n in s.notes:
                ui.hint(n)
        if s.is_ready():
            ui.success("xtool is ready. Run `smart-apple-dev new myapp --lang swift` to start.")
        else:
            ui.warning("xtool is not ready. Run `smart-apple-dev xtool install`.")

    @xtool.command(name="install")
    @click.option("--redownload", is_flag=True,
                  help="Re-download the Swift toolchain even if it's already present")
    @click.option("--yes", "-y", is_flag=True,
                  help="Skip the confirmation prompt (assumes yes)")
    def xtool_install(redownload, yes):
        """Install Swift for Linux and build xtool from source.

        Downloads ~600 MB and compiles for ~5 min. Idempotent: re-running
        is fast if everything is already installed.
        """
        from ..xtool_env import xtool_install as _install, xtool_status as _status
        s = _status()
        if s.is_ready() and not redownload:
            ui.success("xtool is already installed.")
            return
        if not yes:
            print()
            print("This will:")
            print("  1. Download Swift for Linux (~600 MB) from swift.org")
            print("  2. Extract it to ~/.smart-apple-dev/swift/")
            print("  3. Clone the xtool repo to ~/.smart-apple-dev/xtool/")
            print("  4. Build xtool with `swift build` (~5 min)")
            print("  5. Symlink `swift` and `xtool` into ~/.smart-apple-dev/tools/")
            print()
            if not click.confirm("Proceed?", default=False):
                ui.warning("aborted by user")
                sys.exit(1)
        try:
            s2 = _install(redownload=redownload)
        except Exception as e:
            ui.error(f"install failed: {e}")
            sys.exit(1)
        ui.success("xtool installed.")
        if not s2.on_path:
            ui.hint(
                "add ~/.smart-apple-dev/tools to your PATH (or use the symlinks "
                "that `verify.sh` and the CLI already include)"
            )

    @xtool.command(name="uninstall")
    @click.option("--yes", "-y", is_flag=True,
                  help="Skip the confirmation prompt")
    def xtool_uninstall(yes):
        """Remove the xtool environment (Swift toolchain + xtool source)."""
        from ..xtool_env import xtool_uninstall as _uninstall
        if not yes:
            if not click.confirm("Remove ~/.smart-apple-dev/swift and ~/.smart-apple-dev/xtool?", default=False):
                ui.warning("aborted by user")
                sys.exit(1)
        _uninstall()
        ui.success("xtool removed.")

    @xtool.command(name="verify")
    def xtool_verify():
        """Run a build through xtool to confirm the full pipeline works end-to-end."""
        from ..xtool_env import xtool_status as _status
        s = _status()
        if not s.is_ready():
            ui.error("xtool not ready. Run `smart-apple-dev xtool install` first.")
            sys.exit(1)
        # Build a tiny SwiftPM project and run xtool on it
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            pkg = tdp / "Package.swift"
            pkg.write_text(
                '''// swift-tools-version: 5.9
import PackageDescription
let package = Package(
    name: "hello",
    targets: [.executableTarget(name: "hello")]
)
'''
            )
            src = tdp / "Sources" / "hello" / "main.swift"
            src.parent.mkdir(parents=True)
            src.write_text('''
import Foundation
print("Hello from xtool-verified smart-apple-dev!")
''')
            # Run xtool new + xtool dev
            r = subprocess.run(
                [s.xtool_path, "new", str(tdp / "app"),
                 "--package-path", str(tdp)],
                capture_output=True, text=True, timeout=120,
            )
            if r.returncode != 0:
                ui.error(f"xtool new failed: {r.stderr[-500:]}")
                sys.exit(1)
            ui.success("xtool can scaffold an iOS project from a SwiftPM package.")

    @cli.command()
    @click.option("--device", default=None,
                  help="Device UDID (iOS) or serial (Android)")
    @click.option("--ipa", "-f", "ipa_path", default=None, type=click.Path(exists=True),
                  help="Specific .ipa to install (skips build + sign)")
    @click.option("--apk", "apk_path", default=None, type=click.Path(exists=True),
                  help="Specific .apk to install on Android (skips build + sign)")
    @click.option("--platform", "platform", default=None,
                  type=click.Choice(["ios", "android", "auto"]),
                  help="Target platform (default: auto-detect from artifact)")
    def install(device, ipa_path, apk_path, platform):
        """Build, sign, package, and install to a connected device."""
        from ..sign import package_ipa
        from ..device import (
            install_ipa, list_devices,
            install_apk, list_android_devices,
        )

        # Pre-built artifact path
        if apk_path:
            apk = Path(apk_path)
            target_platform = platform or "android"
        elif ipa_path:
            ipa = Path(ipa_path)
            target_platform = platform or "ios"
        else:
            target_platform = platform or "auto"
            root = find_project_root()
            if root is None:
                ui.error("No smartapple.toml found.")
                sys.exit(1)

            config = load_config(root)
            orchestrator = BuildOrchestrator(root)

            # Decide target platform from smartapple.toml
            if target_platform == "auto":
                target_platform = "android" if config.target == "android" else "ios"

            # Build
            ui.step(1, f"Building {config.name} for {target_platform}")
            with ui.spinner("Compiling"):
                build_result = orchestrator.build(config, target=config.target)
            if not build_result.success or build_result.artifact is None:
                ui.error("Build failed")
                for e in build_result.errors:
                    ui.error(f"  {e}")
                sys.exit(1)
            ui.success(f"Built {build_result.artifact.name}")

            if target_platform == "android":
                # APKs are already signed with the debug keystore
                apk = build_result.artifact
            else:
                # Sign
                ui.step(2, "Signing")
                with ui.spinner("Applying ldid ad-hoc signature"):
                    sign_result = sign_artifact(build_result.artifact, config, mode="ad-hoc")
                if not sign_result.success:
                    ui.error("Signing failed")
                    for e in sign_result.errors:
                        ui.error(f"  {e}")
                    sys.exit(1)
                ui.success(f"Signed: {sign_result.artifact_path}")

                # Package
                ui.step(3, "Packaging .ipa")
                with ui.spinner("Zipping"):
                    ipa = package_ipa(sign_result.artifact_path)
                ui.success(f"IPA: {ipa} ({ipa.stat().st_size:,} bytes)")

        if target_platform == "android":
            devs = list_android_devices()
            if not devs:
                ui.warning("No Android devices found.")
                ui.hint("Connect a device with USB debugging enabled, or pass --apk <path>")
                return
            target = device or devs[0].serial
            ui.info(f"Installing to {target} via adb")
            with ui.spinner("Running adb install"):
                ok = install_apk(apk, target, validate_device=False)
            if ok:
                ui.success(f"Installed to {target}")
                ui.summary([("APK", str(apk)), ("Device", target)])
            else:
                ui.error("Install failed")
                ui.hint(f"Try manually: adb -s {target} install {apk}")
                sys.exit(1)
        else:
            # Check for device
            devices = list_devices()
            if not devices:
                ui.warning("No iOS devices found.")
                ui.hint("Connect a device via USB, or run on a Mac with Xcode")
                ui.info("(The .ipa is ready for manual install or App Store upload.)")
                return

            target = device or devices[0].udid
            ui.info(f"Installing to {target}")
            with ui.spinner("Running ideviceinstaller"):
                ok = install_ipa(ipa, target)
            if ok:
                ui.success(f"Installed to {target}")
                ui.summary([("IPA", str(ipa)), ("Device", target)])
            else:
                ui.error("Install failed")
                ui.hint(f"Try manually: ideviceinstaller -u {target} -i {ipa}")
                sys.exit(1)

    @cli.command()
    @click.option("--platform", "platform", default="all",
                  type=click.Choice(["all", "ios", "android"]),
                  help="Which device family to list")
    def devices(platform):
        """List connected iOS and/or Android devices."""
        if platform in ("all", "ios"):
            devs = list_devices()
            if devs:
                ui.info(f"iOS ({len(devs)} device{'s' if len(devs) != 1 else ''}):")
                for d in devs:
                    ui.success(f"  {d.udid}  {d.name} ({d.product}, iOS {d.ios_version})")
            elif platform == "ios":
                ui.warning("No iOS devices found. Connect one and pair trust this Mac/Linux box.")
        if platform in ("all", "android"):
            from ..device import list_android_devices
            androids = list_android_devices()
            if androids:
                if platform == "all":
                    ui.info(f"Android ({len(androids)} device{'s' if len(androids) != 1 else ''}):")
                for d in androids:
                    state_tag = f" [{d.state}]" if d.state and d.state != "device" else ""
                    ui.success(f"  {d.serial}  {d.model or d.product or 'Android'}{state_tag}")
            elif platform == "android":
                ui.warning("No Android devices found. Connect one and run `adb devices` to verify.")

    @cli.command()
    def info():
        """Show system information."""
        ui.banner("smart-apple-dev info")
        rows = [
            ("Platform", get_platform()),
            ("Project root", str(find_project_root() or "(none)")),
        ]
        for name, path in ensure_dirs().items():
            rows.append((f"  {name}", str(path)))
        ui.summary(rows)
        sdks = list_installed_sdks()
        if sdks:
            ui.info(f"Installed SDKs ({len(sdks)}):")
            for sdk in sdks:
                ui.success(f"  {sdk.platform} {sdk.version}: {sdk.path}")
        else:
            ui.warning("No SDKs installed. Run: smart-apple-dev sdk install")

    @cli.group()
    def sdk():
        """Manage Apple SDKs."""
        pass

    @sdk.command(name="list")
    def sdk_list():
        """List installed SDKs."""
        sdks = list_installed_sdks()
        if not sdks:
            ui.warning("No SDKs installed. Run: smart-apple-dev sdk install")
            return
        for s in sdks:
            ui.success(f"  {s.platform} {s.version}: {s.path}")

    @sdk.command(name="install")
    @click.option("--platform", default="iphoneos",
                  type=click.Choice(["iphoneos", "macosx"]))
    @click.option("--version", default=None)
    def sdk_install(platform, version):
        """Download and install an Apple SDK."""
        from ..core.sdk import SDK_VERSIONS
        available = list(SDK_VERSIONS.get(platform, {}).keys())
        if version is None:
            version = available[0] if available else "18.0"
        if version not in SDK_VERSIONS.get(platform, {}):
            ui.error(f"Available versions: {available}")
            sys.exit(1)
        with ui.spinner(f"Downloading SDK {platform} {version}"):
            try:
                install_sdk(platform, version)
            except SdkError as e:
                ui.error(str(e))
                sys.exit(1)
        ui.success(f"Installed SDK {platform} {version}")

    @cli.command()
    def check():
        """Check backend availability."""
        orchestrator = BuildOrchestrator()
        ui.banner("Backend availability")
        for lang in orchestrator.list_backends():
            info = orchestrator.check_backend_availability(lang)
            ui.info(f"\n{lang}:")
            for name, chk in info["checks"].items():
                if chk["available"]:
                    ui.success(f"  {name}: OK")
                else:
                    ui.warning(f"  {name}: MISSING ({chk.get('path') or 'not found'})")


    @cli.command()
    @click.option("--install", "auto_install", is_flag=True,
                  help="Auto-install missing optional tools")
    @click.option("--json", "as_json", is_flag=True,
                  help="Output machine-readable JSON")
    def doctor(auto_install, as_json):
        """Diagnose the local toolchain and report what's missing."""
        from ..doctor import run_checks, print_report, install_all, DoctorReport
        report = run_checks()
        if as_json:
            import json as _json
            data = {
                "platform": report.platform,
                "arch": report.arch,
                "all_ok": report.all_ok,
                "sdk_count": report.sdk_count,
                "device_count": report.device_count,
                "checks": [c.to_dict() for c in report.checks],
                "missing_required": [c.to_dict() for c in report.missing_required],
                "missing_optional": [c.to_dict() for c in report.missing_optional],
            }
            print(_json.dumps(data, indent=2))
            return
        print_report(report)
        if auto_install:
            print()
            print("Auto-installing...")
            n = install_all(report)
            print(f"Installed {n} tool(s).")
            print()
            report = run_checks()
            print_report(report)
        if not report.all_ok:
            sys.exit(1)

    @sdk.command(name="extract")
    @click.option("--platform", default="iphoneos",
                  type=click.Choice(["iphoneos", "macosx"]))
    @click.option("--version", default="18.0")
    @click.option("--output", "-o", default=None)
    def sdk_extract(platform, version, output):
        """Package an Apple SDK from this Mac's Xcode install.

        Run this on a Mac that has Xcode installed. It packages the SDK
        into a tarball that can be moved to Linux/Windows and installed
        with `smart-apple-dev sdk install`.
        """
        from ..core.sdk import extract_sdk_from_macos
        if get_platform() != "macos":
            print("Error: sdk extract must be run on macOS (Xcode required).")
            print("On a Mac: install Xcode, then run:")
            print("  smart-apple-dev sdk extract --platform iphoneos")
            sys.exit(1)
        try:
            info = extract_sdk_from_macos(Path("/"), platform, version)
            print(f"Extracted: {info.path}")
        except SdkError as e:
            print(f"Error: {e}")
            sys.exit(1)


    @cli.group()
    def provider():
        """Manage build providers."""
        pass

    @provider.command(name="list")
    def provider_list():
        """List all available providers and their status."""
        from ..build.provider import get_registry
        reg = get_registry()
        ui.banner("Build providers")
        for p in reg.list_all():
            available, reason = p.is_available()
            label = f"{p.name:14s}  {p.description}"
            if available:
                ui.success(label)
            else:
                ui.warning(label)
                ui.info(f"      {reason}")
            caps = p.capabilities()
            ui.info(
                f"      build={caps.build} sign={caps.sign} install={caps.install} "
                f"upload={caps.upload}  cost=${caps.cost_per_build:.2f}/build"
            )
            ui.info(f"      languages: {', '.join(caps.languages)}")

    @provider.command(name="default")
    def provider_default():
        """Show the default provider."""
        from ..build.provider import get_registry
        reg = get_registry()
        p = reg.get_default()
        available, reason = p.is_available()
        print(f"Default: {p.name} ({'available' if available else 'unavailable'})")


    @cli.command()
    @click.argument("request", required=False)
    @click.option("--provider", "-p", default="auto",
                  help="LLM provider (use 'auto', 'list', or 'base:label' like 'copilot:backup')")
    @click.option("--model", "-m", default=None, help="Model name override")
    @click.option("--max-iterations", default=15, help="Max agent loop iterations")
    @click.option("--quiet", "-q", is_flag=True, help="Don't show thinking/tool output")
    @click.option("--plan", default=None, help="Path to JSON plan file (for deterministic runs)")
    def agent(request, provider, model, max_iterations, quiet, plan):
        """Run the LLM agent.

        With REQUEST: one-shot mode - runs the agent to completion.
        Without REQUEST: starts an interactive REPL.

        The agent can build, sign, install, and deploy iOS/macOS apps
        using a toolbelt of CLI commands. Supports 21 LLM providers:
          Local (no key):    ollama, lmstudio
          Cloud (API key):   anthropic, openai, gemini, copilot, groq,
                             mistral, together, xai, deepseek, perplexity,
                             sambanova, opencode, nous, cline, kilo, minimax
          Configurable:      custom, gateway
          Testing:           none (deterministic plan-based runs)

        Named instances: Configure multiple instances of the same provider.
          Example: --provider copilot:backup or --provider custom:venice
          Use: smart-apple-dev provider add <name>
        """
        from ..agent.loop import (
            run_agent, run_agent_with_provider_plan, AgentConfig,
            _set_active_provider_override, _clear_active_provider_override,
        )
        from ..agent.llm import (
            make_provider_from_instance, list_example_instances, list_named_instances,
            _PROVIDERS,
        )
        from ..agent.tools import get_tools
        from pathlib import Path as _P

        # Handle --provider list
        if provider == "list":
            _print_provider_list()
            return

        # Resolve named instance if specified (e.g. "copilot:backup", "custom:venice")
        configured_instance = None
        if ":" in provider:
            configured_instance = make_provider_from_instance(provider)
            if configured_instance is None:
                print(f"Error: Named provider '{provider}' not configured.")
                print()
                print("Available named instances:")
                for inst in sorted(list_named_instances().keys()):
                    print(f"  - {inst}")
                if not list_named_instances():
                    print("  (none configured yet)")
                print()
                print("Examples you can add:")
                for name, cfg in sorted(list_example_instances().items()):
                    print(f"  {name:<25} {cfg.get('description', '')}")
                sys.exit(1)

        cfg = AgentConfig(
            max_iterations=max_iterations,
            show_thinking=not quiet,
            show_tool_results=not quiet,
            provider_name=provider,
            model=model,
        )

        # If we have a configured named instance, set the override
        if configured_instance is not None:
            _set_active_provider_override(configured_instance)

        if plan:
            plan_path = _P(plan)
            if not plan_path.exists():
                print(f"Error: plan file {plan} not found")
                sys.exit(1)
            with open(plan_path) as f:
                plan_data = json.load(f)
            result = run_agent_with_provider_plan(plan_data, config=cfg)
        elif request:
            result = run_agent(request, config=cfg)
        else:
            # Interactive REPL
            print("smart-apple-dev agent (REPL mode)")
            print("Type your request, or 'exit' to quit, 'tools' to list tools.")
            print()
            while True:
                try:
                    user_input = input("> ")
                except (EOFError, KeyboardInterrupt):
                    print()
                    break
                user_input = user_input.strip()
                if not user_input:
                    continue
                if user_input in ("exit", "quit", "q"):
                    break
                if user_input == "tools":
                    for name, t in get_tools().items():
                        print(f"  {name}: {t.description[:60]}")
                    continue
                if user_input == "provider":
                    from ..agent.llm import auto_select_provider
                    p = auto_select_provider()
                    ok, why = p.is_available()
                    print(f"  {p.name}: {'available' if ok else why}")
                    continue
                print()
                result = run_agent(user_input, config=cfg)
                print()
                print(f"[done in {result.iterations} iterations, {result.tool_calls_made} tool calls]")

        # Clear override
        _clear_active_provider_override()

        # Print final summary
        if not result.success:
            print(f"\\n[error] {result.final_message}")
            for e in result.errors:
                print(f"  - {e}")
            sys.exit(1)
        else:
            print(f"\\n[success] {result.final_message}")
            print(f"  iterations: {result.iterations}")
            print(f"  tool calls: {result.tool_calls_made}")
            print(f"  tokens:     {result.tokens_used}")

    # ---- LLM provider named-instance management ----
    # These commands are for LLM providers (not build providers).
    # They manage ~/.smart-apple-dev/llm-providers.json

    def _print_provider_list() -> None:
        """Print all LLM providers with their named instances in a hierarchy."""
        from ..agent.llm import (
            list_providers, get_provider_class, list_models_for, KNOWN_MODELS,
            auto_select_provider, list_providers_grouped, list_named_instances,
            list_example_instances, get_instance_config, _resolve_env_ref,
            _PROVIDERS,
        )
        auto_p = auto_select_provider()
        grouped = list_providers_grouped()

        print("Available LLM providers:")
        print()

        seen_bases = set()
        for base_name in list_providers_grouped().keys():
            if ":" in base_name and not _PROVIDERS.get(base_name.split(":", 1)[0]):
                continue
            if base_name in seen_bases:
                continue
            seen_bases.add(base_name)

            items = grouped[base_name]
            cls = get_provider_class(base_name)
            try:
                inst = cls()
                available, reason = inst.is_available()
                status = "[+] available" if available else f"[-] {reason[:30]}"
                model = cls.default_model or "(none)"
                base = inst.base_url or "-"
                auto_mark = " *" if base_name == auto_p.name else ""
                print(f"  {base_name:<18}{auto_mark:<3} {status}")
                if model:
                    print(f"  {'':<18}    model: {model}")
                if base != "-":
                    print(f"  {'':<18}    url:   {base}")
            except Exception as e:
                print(f"  {base_name:<18}  [-] error: {e}")

            for item in items[1:]:
                cfg = get_instance_config(item) or {}
                label = item.split(":", 1)[1] if ":" in item else item
                desc = cfg.get("description", "")
                model = cfg.get("default_model", "")
                base_url = cfg.get("base_url", "")
                api_key_ref = cfg.get("api_key", "")
                resolved = _resolve_env_ref(api_key_ref) if api_key_ref else ""
                has_key = bool(resolved and resolved != api_key_ref)
                key_status = "[+]" if has_key else "[-]"
                print(f"    [LABEL] {label:<15} {desc}")
                if model:
                    print(f"           {'':<15} model: {model}")
                if base_url:
                    print(f"           {'':<15} url:   {base_url}")
                print(f"           {'':<15} key:   {key_status} {api_key_ref}")
            print()

        print(f"  [*] = auto-selected ({auto_p.name})")
        print()
        print("Named instance syntax: --provider 'base:label' (e.g. 'custom:venice', 'copilot:backup')")
        print()
        print(f"Models for {auto_p.name}:")
        models = list_models_for(auto_p.name, base_url=auto_p.base_url)
        if models:
            for m in models[:15]:
                print(f"  - {m}")
            if len(models) > 15:
                print(f"  ... and {len(models)-15} more")
        else:
            known = KNOWN_MODELS.get(auto_p.name, [])
            if known:
                print(f"  (from known list: {', '.join(known[:5])})")
        examples = list_example_instances()
        if examples:
            print()
            print("Example instances you can add with --provider-add:")
            for name, cfg in examples.items():
                print(f"  {name:<25} {cfg.get('description', '')}")

    @provider.command(name="add")
    @click.argument("name")
    @click.option("--base-url", default=None, help="API base URL (e.g. https://api.venice.ai/v1)")
    @click.option("--api-key", default=None, help="API key (or ${ENV_VAR} to reference an env var)")
    @click.option("--model", default=None, help="Default model")
    @click.option("--description", default="", help="Description of this instance")
    def provider_add(name, base_url, api_key, model, description):
        """Add a named LLM provider instance.

        NAME is 'base:label', e.g.:
          copilot:default   (a Copilot instance named 'default')
          copilot:backup    (another Copilot instance)
          custom:venice     (Venice.ai as a custom provider)
          custom:openrouter (OpenRouter as custom)

        After adding, use it with:
          smart-apple-dev agent --provider '{name}'
        """
        from ..agent.llm import (
            set_instance_config, list_example_instances, get_provider_class, _PROVIDERS,
            list_named_instances,
        )
        if ":" not in name:
            print("Error: NAME must include a ':' separator (e.g. 'copilot:default')")
            print("  Format: base:label  where base is the provider class and label is your name")
            sys.exit(1)
        base, label = name.split(":", 1)
        if base not in _PROVIDERS:
            print(f"Error: Unknown base provider '{base}'.")
            print(f"  Available: {', '.join(sorted(_PROVIDERS.keys()))}")
            sys.exit(1)
        existing = list_named_instances()
        if name in existing:
            print(f"Warning: '{name}' already exists. Updating.")
            existing_cfg = existing[name]
        else:
            existing_cfg = {}
        cfg = dict(existing_cfg)
        if base_url:
            cfg["base_url"] = base_url
        elif not cfg.get("base_url"):
            example = list_example_instances().get(name)
            if example:
                cfg["base_url"] = example.get("base_url", "")
            else:
                print(f"Error: --base-url is required for new instance '{name}'")
                sys.exit(1)
        if api_key:
            cfg["api_key"] = api_key
        if model:
            cfg["default_model"] = model
        if description:
            cfg["description"] = description
        set_instance_config(name, cfg)
        print(f"Saved: {name}")
        print(f"  base:  {base}")
        print(f"  label: {label}")
        print(f"  url:   {cfg.get('base_url', '')}")
        print(f"  key:   {cfg.get('api_key', '')}")
        print(f"  model: {cfg.get('default_model', '')}")
        print()
        print(f"Use: smart-apple-dev agent --provider '{name}'")

    @provider.command(name="del")
    @click.argument("name")
    def provider_del(name):
        """Delete a named LLM provider instance.

        Example:
          smart-apple-dev provider del copilot:backup
        """
        from ..agent.llm import delete_instance_config, list_named_instances
        instances = list_named_instances()
        if name not in instances:
            print(f"Error: '{name}' not found.")
            print(f"  Available: {', '.join(sorted(instances.keys()))}")
            sys.exit(1)
        delete_instance_config(name)
        print(f"Deleted: {name}")

    @provider.command(name="list-instances")
    def provider_list_instances():
        """List all named LLM provider instances."""
        from ..agent.llm import list_named_instances, get_instance_config
        instances = list_named_instances()
        if not instances:
            print("No named instances configured.")
            print("  Use: smart-apple-dev provider add <name>")
            return
        for inst_name, cfg in sorted(instances.items()):
            print(f"  {inst_name}")
            for k, v in cfg.items():
                print(f"    {k}: {v}")
            print()

    # ---- LLM provider list in agent command ----
    # Update agent's provider list option
    # (done by updating the click.Choice below)

    return cli

def cli(args=None):

    """Entry point. Called by the console script and by tests."""
    if args is not None:
        import sys as _sys
        old_argv = _sys.argv
        _sys.argv = ["smart-apple-dev"] + list(args)
        try:
            create_cli()()
        finally:
            _sys.argv = old_argv
    else:
        create_cli()()
if __name__ == "__main__":
    cli()
