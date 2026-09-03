"""Tests for the verify/ scripts and the docs site structure.

Static-only — we don't actually run gradle, sdkmanager, or ldid here;
we just confirm the scripts are syntactically valid, executable,
and reference the right paths.
"""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


class TestVerifyScripts:
    def test_verify_sh_exists(self):
        p = REPO / "verify" / "verify.sh"
        assert p.exists()

    def test_verify_sh_is_executable(self):
        p = REPO / "verify" / "verify.sh"
        assert os.access(p, os.X_OK), f"{p} should be chmod +x"

    def test_verify_sh_syntax_valid(self):
        import subprocess
        r = subprocess.run(["bash", "-n", str(REPO / "verify" / "verify.sh")],
                           capture_output=True, text=True)
        assert r.returncode == 0, f"bash -n failed: {r.stderr}"

    def test_verify_android_sh_exists(self):
        p = REPO / "verify" / "verify-android.sh"
        assert p.exists()

    def test_verify_android_sh_is_executable(self):
        p = REPO / "verify" / "verify-android.sh"
        assert os.access(p, os.X_OK), f"{p} should be chmod +x"

    def test_verify_android_sh_syntax_valid(self):
        import subprocess
        r = subprocess.run(["bash", "-n", str(REPO / "verify" / "verify-android.sh")],
                           capture_output=True, text=True)
        assert r.returncode == 0, f"bash -n failed: {r.stderr}"

    def test_setup_windows_ps1_exists(self):
        p = REPO / "verify" / "setup-windows.ps1"
        assert p.exists()

    def test_windows_md_exists(self):
        p = REPO / "verify" / "WINDOWS.md"
        assert p.exists()

    def test_verify_android_references_hello_kotlin(self):
        text = (REPO / "verify" / "verify-android.sh").read_text()
        assert "hello-kotlin" in text

    def test_verify_android_checks_android_home(self):
        text = (REPO / "verify" / "verify-android.sh").read_text()
        assert "ANDROID_HOME" in text
        assert "java" in text  # JDK check

    def test_verify_sh_kotlin_branch_calls_android_script(self):
        """When --lang kotlin is run and ANDROID_HOME is set, verify.sh should delegate to verify-android.sh."""
        text = (REPO / "verify" / "verify.sh").read_text()
        # Find the kotlin case
        m = re.search(r"kotlin\)(.*?)\*\)", text, re.DOTALL)
        assert m, "no kotlin case in verify.sh language switch"
        case = m.group(1)
        assert "verify-android.sh" in case
        assert "ANDROID_HOME" in case or "ANDROID_SDK_ROOT" in case


class TestMkDocsConfig:
    def test_mkdocs_yml_exists(self):
        assert (REPO / "mkdocs.yml").exists()

    def test_mkdocs_yml_has_required_keys(self):
        import yaml
        with open(REPO / "mkdocs.yml") as f:
            config = yaml.safe_load(f)
        assert "site_name" in config
        assert "nav" in config
        assert "theme" in config
        assert config["site_name"] == "smart-apple-dev"

    def test_mkdocs_nav_includes_android(self):
        import yaml
        with open(REPO / "mkdocs.yml") as f:
            config = yaml.safe_load(f)
        # The nav should reference the android.md page
        nav_str = str(config["nav"])
        assert "android" in nav_str.lower()

    def test_mkdocs_nav_includes_all_pages(self):
        import yaml
        with open(REPO / "mkdocs.yml") as f:
            config = yaml.safe_load(f)
        nav_str = str(config["nav"])
        # Every .md file in docs/ should be reachable
        docs = {p.stem for p in (REPO / "docs").glob("*.md")}
        for stem in docs:
            assert stem in nav_str or any(stem in str(s) for s in config["nav"]), \
                f"{stem}.md not in nav"


class TestDocsPages:
    """Each docs/*.md page should be non-empty, have a heading, and not
    contain broken cross-links.
    """

    def test_all_pages_have_h1(self):
        # Collect every page file referenced
        page_files = {p for p in (REPO / "docs").glob("*.md")}
        for page in page_files:
            text = page.read_text()
            assert text.lstrip().startswith("# "), f"{page.name} has no H1"

    def test_android_page_mentions_gradlew(self):
        text = (REPO / "docs" / "android.md").read_text()
        assert "assembleDebug" in text
        assert "ANDROID_HOME" in text

    def test_verifying_page_references_scripts(self):
        text = (REPO / "docs" / "verifying.md").read_text()
        assert "verify.sh" in text
        assert "verify-android.sh" in text

    def test_no_root_relative_links(self):
        """All ../X.md cross-links should be GitHub blob URLs (Phase 5 fix)."""
        for page in (REPO / "docs").glob("*.md"):
            text = page.read_text()
            for m in re.finditer(r"\(\.\./[A-Z_]+\.md\)", text):
                raise AssertionError(
                    f"{page.name} still has root-relative link {m.group(0)}; use a GitHub URL"
                )


class TestGitHubWorkflows:
    """The CI workflows should be valid YAML and reference the right jobs."""

    def test_ci_yml_has_android_job(self):
        import yaml
        with open(REPO / ".github" / "workflows" / "ci.yml") as f:
            config = yaml.safe_load(f)
        assert "android" in config["jobs"], "ci.yml should have an android job"

    def test_docs_yml_exists(self):
        assert (REPO / ".github" / "workflows" / "docs.yml").exists()

    def test_docs_yml_deploys_pages(self):
        import yaml
        with open(REPO / ".github" / "workflows" / "docs.yml") as f:
            config = yaml.safe_load(f)
        assert "jobs" in config
        assert "deploy" in config["jobs"]
        # Uses actions/deploy-pages
        deploy_steps = config["jobs"]["deploy"]["steps"]
        assert any("deploy-pages" in str(s) for s in deploy_steps)

    def test_release_yml_exists(self):
        assert (REPO / ".github" / "workflows" / "release.yml").exists()

    def test_release_yml_triggers_on_tag(self):
        import yaml
        with open(REPO / ".github" / "workflows" / "release.yml") as f:
            config = yaml.safe_load(f)
        # Should be tagged push or workflow_dispatch with tag input
        on = config[True] if True in config else config["on"]
        assert "push" in on or "tags" in str(on).lower()
