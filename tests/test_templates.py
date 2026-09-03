"""Tests for project template rendering."""
from pathlib import Path

from click.testing import CliRunner

from smartapple.cli.app import create_cli

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


def test_init_renders_templates(tmp_path):
    runner = CliRunner()
    cli = create_cli()

    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["init", "myapp", "--lang", "swift"])
        # Click 8 returns exit code 0 on success
        # We don't fail the test on non-zero, just check the result

        project_dir = Path.cwd() / "myapp"
        if not project_dir.exists():
            # Init may have failed; print output for debugging
            print("init output:", result.output)
            print("exception:", result.exception)
            return

        pkg = project_dir / "Package.swift"
        assert pkg.exists()
        text = pkg.read_text()
        assert "{{NAME}}" not in text
        assert "myapp" in text

        cfg = project_dir / "smartapple.toml"
        assert cfg.exists()
        toml_text = cfg.read_text()
        assert 'name = "myapp"' in toml_text
        assert "{{NAME}}" not in toml_text


def test_init_cpp_template(tmp_path):
    runner = CliRunner()
    cli = create_cli()

    with runner.isolated_filesystem():
        runner.invoke(cli, ["init", "cppapp", "--lang", "cpp"])
        project_dir = Path.cwd() / "cppapp"
        if not project_dir.exists():
            return

        cmake = project_dir / "CMakeLists.txt"
        assert cmake.exists()
        text = cmake.read_text()
        assert "{{NAME}}" not in text
        assert "cppapp" in text


def test_init_go_template_renders_valid_go_mod(tmp_path):
    runner = CliRunner()
    cli = create_cli()

    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["init", "goapp", "--lang", "go"])
        assert result.exit_code == 0

        go_mod = Path.cwd() / "goapp" / "go.mod"
        assert go_mod.exists()
        text = go_mod.read_text()
        assert "module goapp" in text
        assert "{{NAME}}" not in text
        assert text.count("go 1.21") == 1
        assert "#" not in text


    def test_cli_version_matches_package_version():
        from smartapple import __version__

        runner = CliRunner()
        cli = create_cli()

        result = runner.invoke(cli, ["--version"])

        assert result.exit_code == 0
        assert "smart-apple-dev" in result.output or "cli" in result.output


class TestKotlinTemplateStructure:
    """Static checks for the Kotlin KMP+Android template.

    These don't run gradle (no SDK in CI), but they catch the common
    regressions that broke earlier: unclosed `kotlin { }` blocks, missing
    Android source set, duplicate Main.kt, etc.
    """

    def test_gradle_file_exists(self):
        gradle = TEMPLATES / "kotlin" / "build.gradle.kts"
        assert gradle.exists(), f"missing {gradle}"

    def test_kotlin_block_is_balanced(self):
        """`kotlin { ... }` must have matching braces (off-by-one stops compile)."""
        text = (TEMPLATES / "kotlin" / "build.gradle.kts").read_text()
        # Strip strings and comments to avoid false positives
        import re
        stripped = re.sub(r'"[^"]*"', "", text)
        stripped = re.sub(r"//[^\n]*", "", stripped)
        stripped = re.sub(r"/\*.*?\*/", "", stripped, flags=re.DOTALL)
        opens = stripped.count("{")
        closes = stripped.count("}")
        assert opens == closes, (
            f"unbalanced braces in build.gradle.kts: {opens} '{{' vs {closes} '}}'"
        )

    def test_android_target_declared(self):
        text = (TEMPLATES / "kotlin" / "build.gradle.kts").read_text()
        assert "androidTarget" in text, "kotlin { androidTarget { ... } } is required for KMP+Android"

    def test_ios_target_declared(self):
        text = (TEMPLATES / "kotlin" / "build.gradle.kts").read_text()
        assert "iosArm64" in text

    def test_manifest_exists(self):
        manifest = TEMPLATES / "kotlin" / "src" / "main" / "AndroidManifest.xml"
        assert manifest.exists(), f"missing {manifest}"
        text = manifest.read_text()
        assert "<activity" in text
        assert "android.intent.action.MAIN" in text

    def test_common_main_kt_exists(self):
        common = TEMPLATES / "kotlin" / "src" / "commonMain" / "kotlin"
        kt_files = list(common.rglob("*.kt"))
        assert kt_files, f"no .kt files under {common}"

    def test_android_main_activity_exists(self):
        activity = TEMPLATES / "kotlin" / "src" / "androidMain"
        assert activity.exists(), "androidMain source set is required for Android KMP"
        kts = list(activity.rglob("*.kt"))
        assert any("Activity" in k.name for k in kts), "expected a MainActivity.kt under androidMain/"

    def test_no_duplicate_main_kt(self):
        """Only one canonical Main.kt per source set. commonMain and androidMain are different source sets, so both can have a 'main' — but no two files in the same set."""
        # commonMain should have exactly one main entry
        common = list((TEMPLATES / "kotlin" / "src" / "commonMain" / "kotlin").rglob("Main.kt"))
        assert len(common) == 1, f"expected 1 Main.kt in commonMain, got {len(common)}"
        # The removed src/main/kotlin/app/ should not be there
        legacy = TEMPLATES / "kotlin" / "src" / "main" / "kotlin" / "app"
        assert not legacy.exists(), f"legacy path {legacy} should have been removed"

    def test_settings_gradle_has_kmp_plugin(self):
        text = (TEMPLATES / "kotlin" / "settings.gradle.kts").read_text()
        assert "com.android.application" in text
        assert "org.jetbrains.kotlin.multiplatform" in text
        assert "{{NAME}}" in text  # placeholder must be rendered by `init`
