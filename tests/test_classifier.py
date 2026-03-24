"""Tests for the classifier service."""

from code_adapt.models import Classification, DiffStats
from code_adapt.services.classifier import (
    classify_change,
    extract_intent,
    extract_modules,
    generate_summary,
)


class TestClassifyChange:
    def test_security(self):
        assert classify_change("Fix CVE-2024-1234", [], 10, 5) == Classification.SECURITY

    def test_security_file(self):
        assert classify_change("update deps", ["security/patch.py"], 10, 5) == Classification.SECURITY

    def test_bugfix(self):
        assert classify_change("fix: resolve null pointer", [], 10, 5) == Classification.BUGFIX

    def test_refactor(self):
        assert classify_change("refactor: extract helper", [], 10, 5) == Classification.REFACTOR

    def test_feature_keyword(self):
        assert classify_change("feat: add user dashboard", [], 10, 5) == Classification.FEATURE

    def test_feature_by_additions(self):
        assert classify_change("update things", [], 200, 10) == Classification.FEATURE

    def test_unknown(self):
        assert classify_change("update version", [], 1, 1) == Classification.UNKNOWN


class TestExtractModules:
    def test_src_prefix(self):
        assert extract_modules(["src/models/user.py", "src/models/auth.py"]) == ["models"]

    def test_root_files(self):
        assert extract_modules(["README.md"]) == ["root"]

    def test_top_level_dirs(self):
        assert extract_modules(["tests/test_foo.py", "docs/guide.md"]) == ["docs", "tests"]


class TestGenerateSummary:
    def test_basic(self):
        stats = DiffStats(additions=10, deletions=5, files_changed=3)
        result = generate_summary("add user login", Classification.FEATURE, stats)
        assert result == "Feature: add user login (+10/-5 in 3 files)"

    def test_single_file(self):
        stats = DiffStats(additions=1, deletions=0, files_changed=1)
        result = generate_summary("fix typo", Classification.BUGFIX, stats)
        assert "1 file)" in result


class TestExtractIntent:
    def test_first_sentence(self):
        assert extract_intent("Fix the login bug. Also updated docs.") == "Fix the login bug."

    def test_first_line(self):
        assert extract_intent("Update README\n\nMore details here") == "Update README"
