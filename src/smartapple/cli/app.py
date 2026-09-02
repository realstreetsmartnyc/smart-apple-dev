"""smart-apple-dev CLI application."""

import json
import sys
from pathlib import Path

try:
    import click
except ImportError:
    click = None

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
            print(f"Error: {name} already exists")
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
            print(f"Error: no template found for language '{lang}'")
            sys.exit(1)

        # Template variables for substitution
        template_vars = {
            "{{NAME}}": name,
            "{{BUNDLE_ID}}": bundle,
        }

        def render(text: str) -> str:
            for k, v in template_vars.items():
                text = text.replace(k, v)
            return text

        def copy_template(src: Path, dst: Path) -> None:
            if src.is_file():
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(render(src.read_text()))
            elif src.is_dir():
                dst.mkdir(parents=True, exist_ok=True)
                for child in src.iterdir():
                    copy_template(child, dst / child.name)

        for item in template_dir.iterdir():
            copy_template(item, project_dir / item.name)

        print(f"Created {name} ({lang}) at {project_dir}")
        print(f"Config: {config_path}")
        print(f"Next: cd {name} && smart-apple-dev build")

    @cli.command()
    @click.option("--target", default="ios",
                  type=click.Choice(["ios", "ios-simulator", "macos", "catalyst"]),
                  help="Build target")
    @click.option("--release", is_flag=True, help="Release build")
    @click.option("--provider", default=None,
                  help="Build provider (default: auto-detect)")
    def build(target, release, provider):
        """Build the current project."""
        root = find_project_root()
        if root is None:
            print("Error: No smartapple.toml found. Run 'smart-apple-dev init' first.")
            sys.exit(1)

        config = load_config(root)
        from ..build.provider import get_provider
        prov = get_provider(provider)
        available, reason = prov.is_available()
        if not available:
            print(f"Provider '{prov.name}' not available: {reason}")
            sys.exit(1)
        result = prov.build(root, config, target=target, release=release)

        if result.success:
            print(f"Build succeeded via {prov.name} ({result.metadata.get('language', '')})")
            if result.artifact:
                print(f"Artifact: {result.artifact}")
            if result.duration_seconds:
                print(f"Duration: {result.duration_seconds:.1f}s")
        else:
            print(f"Build failed via {prov.name}")
            for err in result.errors:
                print(f"  Error: {err}")
            if result.output:
                print(f"Output: {result.output[:500]}")
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
                  help="After signing, package the .app into a .ipa")
    @click.option("--target", "-t", default=None,
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
            print(f"  warning: {w}")

        if not sign_result.success:
            print("Signing failed:")
            for err in sign_result.errors:
                print(f"  Error: {err}")
            sys.exit(1)

        if sign_result.signed:
            print(f"Signed: {sign_result.artifact_path}")
        else:
            print(f"Build OK but not signed: {sign_result.artifact_path}")
            for w in sign_result.warnings:
                print(f"  {w}")

        if to_ipa:
            ipa_path = package_ipa(sign_result.artifact_path)
            print(f"IPA: {ipa_path} ({ipa_path.stat().st_size:,} bytes)")

    @cli.command()
    @click.option("--device", default=None, help="Device UDID")
    @click.option("--ipa", "-f", "ipa_path", default=None, type=click.Path(exists=True),
                  help="Specific .ipa to install (skips build + sign)")
    def install(device, ipa_path):
        """Build, sign, package, and install to a connected device."""
        from ..sign import package_ipa
        from ..device import install_ipa, list_devices

        if ipa_path:
            ipa = Path(ipa_path)
        else:
            root = find_project_root()
            if root is None:
                print("Error: No smartapple.toml found.")
                sys.exit(1)

            config = load_config(root)
            orchestrator = BuildOrchestrator(root)

            # Build
            print(f"[1/3] Building {config.name}...")
            build_result = orchestrator.build(config)
            if not build_result.success or build_result.artifact is None:
                print("Build failed.")
                sys.exit(1)
            print(f"  Build OK: {build_result.artifact}")

            # Sign
            print(f"[2/3] Signing...")
            sign_result = sign_artifact(build_result.artifact, config, mode="ad-hoc")
            if not sign_result.success:
                print("Signing failed.")
                sys.exit(1)
            print(f"  Sign OK: {sign_result.artifact_path}")

            # Package
            print(f"[3/3] Packaging .ipa...")
            ipa = package_ipa(sign_result.artifact_path)
            print(f"  IPA: {ipa} ({ipa.stat().st_size:,} bytes)")

        # Check for device
        devices = list_devices()
        if not devices:
            print("No iOS devices found. Connect one via USB, or run on a Mac with Xcode.")
            print("(The .ipa is ready for manual install or App Store upload.)")
            return

        target = device or devices[0].udid
        print(f"Installing to {target}...")
        if install_ipa(ipa, target):
            print(f"Installed to {target}")
        else:
            print("Install failed.")
            print("(You can try manually: ideviceinstaller -u <udid> -i <ipa>)")
            sys.exit(1)

    @cli.command()
    def devices():
        """List connected iOS devices."""
        devs = list_devices()
        if not devs:
            print("No devices found. Connect an iOS device.")
            return
        for d in devs:
            print(f"  {d.udid} - {d.name} ({d.product}, iOS {d.ios_version})")

    @cli.command()
    def info():
        """Show system information."""
        print(f"Platform: {get_platform()}")
        print(f"Project root: {find_project_root()}")
        dirs = ensure_dirs()
        for name, path in dirs.items():
            print(f"  {name}: {path}")
        print(f"\nInstalled SDKs:")
        for sdk in list_installed_sdks():
            print(f"  {sdk.platform} {sdk.version}: {sdk.path}")

    @cli.group()
    def sdk():
        """Manage Apple SDKs."""
        pass

    @sdk.command(name="list")
    def sdk_list():
        """List installed SDKs."""
        sdks = list_installed_sdks()
        if not sdks:
            print("No SDKs installed.")
            print("Run 'smart-apple-dev sdk install' to download one.")
            return
        for s in sdks:
            print(f"  {s.platform} {s.version}: {s.path}")

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
            print(f"Available versions: {available}")
            sys.exit(1)
        try:
            install_sdk(platform, version)
        except SdkError as e:
            print(f"Error: {e}")
            sys.exit(1)

    @cli.command()
    def check():
        """Check backend availability."""
        orchestrator = BuildOrchestrator()
        for lang in orchestrator.list_backends():
            info = orchestrator.check_backend_availability(lang)
            print(f"\n{lang}:")
            for name, check in info["checks"].items():
                status = "OK" if check["available"] else "MISSING"
                print(f"  {name}: {status}")


    @cli.command()
    @click.option("--install", "auto_install", is_flag=True,
                  help="Auto-install missing optional tools")
    def doctor(auto_install):
        """Diagnose the local toolchain and report what's missing."""
        from ..doctor import run_checks, print_report, install_all
        report = run_checks()
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
        print("Registered providers:")
        for p in reg.list_all():
            available, reason = p.is_available()
            mark = "✓" if available else "✗"
            print(f"  {mark} {p.name:12s}  {p.description}")
            if not available:
                print(f"      {reason}")
            caps = p.capabilities()
            print(f"      build={caps.build} sign={caps.sign} install={caps.install} upload={caps.upload}")
            print(f"      languages: {', '.join(caps.languages)}")
            print(f"      cost: ${caps.cost_per_build:.2f}/build")

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
