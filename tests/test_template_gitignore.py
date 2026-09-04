"""Tests for template .gitignore files.

Each template should provide a .gitignore so user projects ignore
language-specific build artifacts, IDE files, etc.
"""

import os
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"

# Patterns that every .gitignore should have for the language
REQUIRED_PATTERNS = {
    "swift": [".build/", "Packages/"],
    "kotlin": ["build/", ".gradle/", "*.apk"],
    "godot": [".godot/"],
    "cpp": ["build/", "*.o", "CMakeFiles/"],
    "go": ["bin/", "vendor/"],
    "rust": ["/target/"],
    "objc": ["build/", "Pods/"],
}


class TestTemplateGitignore:
    """Every language template ships a .gitignore."""

    def test_all_templates_have_gitignore(self):
        missing = []
        for lang_dir in TEMPLATES.iterdir():
            if not lang_dir.is_dir():
                continue
            gi = lang_dir / ".gitignore"
            if not gi.exists():
                missing.append(lang_dir.name)
        assert not missing, f"missing .gitignore in: {missing}"

    def test_no_template_gitignore_is_empty(self):
        empty = []
        for lang_dir in TEMPLATES.iterdir():
            if not lang_dir.is_dir():
                continue
            gi = lang_dir / ".gitignore"
            if gi.exists() and gi.stat().st_size == 0:
                empty.append(lang_dir.name)
        assert not empty, f"empty .gitignore in: {empty}"

    def test_gitignore_ignores_build_dirs(self):
        for lang, required in REQUIRED_PATTERNS.items():
            gi = TEMPLATES / lang / ".gitignore"
            assert gi.exists(), f"no .gitignore in {lang}/"
            text = gi.read_text()
            for pattern in required:
                assert pattern in text, (
                    f"missing '{pattern}' in {lang}/.gitignore. "
                    f"Got: {text!r}"
                )
