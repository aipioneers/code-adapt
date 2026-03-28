"""Tests for multi-provider wiring in Repository model and CLI commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
import yaml

from code_adapt.models import Repository
from code_adapt.services.provider import Provider, detect_provider


# ---------------------------------------------------------------------------
# Repository model: provider field
# ---------------------------------------------------------------------------


class TestRepositoryProviderField:
    def test_default_provider_is_github(self):
        repo = Repository(name="myrepo", url="https://github.com/a/b", type="upstream")
        assert repo.provider == "github"

    def test_explicit_provider_gitlab(self):
        repo = Repository(
            name="glrepo",
            url="https://gitlab.com/a/b",
            type="upstream",
            provider="gitlab",
        )
        assert repo.provider == "gitlab"

    def test_explicit_provider_gitcode(self):
        repo = Repository(
            name="gcrepo",
            url="https://gitcode.com/a/b",
            type="upstream",
            provider="gitcode",
        )
        assert repo.provider == "gitcode"

    def test_provider_in_model_dump(self):
        repo = Repository(
            name="myrepo",
            url="https://github.com/a/b",
            type="upstream",
            provider="gitlab",
        )
        data = repo.model_dump()
        assert "provider" in data
        assert data["provider"] == "gitlab"

    def test_backward_compat_no_provider_in_yaml(self):
        """Existing repos.yaml entries without 'provider' should default to 'github'."""
        data = {
            "name": "old-repo",
            "url": "https://github.com/a/b",
            "type": "upstream",
            "default_branch": "main",
        }
        repo = Repository(**data)
        assert repo.provider == "github"

    def test_provider_roundtrip(self):
        repo = Repository(
            name="test",
            url="https://gitlab.com/a/b",
            type="upstream",
            provider="gitlab",
        )
        dumped = repo.model_dump()
        restored = Repository(**dumped)
        assert restored.provider == "gitlab"


# ---------------------------------------------------------------------------
# Provider auto-detection integration
# ---------------------------------------------------------------------------


class TestProviderAutoDetection:
    def test_github_url_detected(self):
        assert detect_provider("https://github.com/owner/repo").value == "github"

    def test_gitlab_url_detected(self):
        assert detect_provider("https://gitlab.com/owner/repo").value == "gitlab"

    def test_gitcode_url_detected(self):
        assert detect_provider("https://gitcode.com/owner/repo").value == "gitcode"

    def test_unknown_url_detected(self):
        assert detect_provider("https://my-server.example.com/owner/repo").value == "unknown"

    def test_ssh_github_detected(self):
        assert detect_provider("git@github.com:owner/repo.git").value == "github"

    def test_ssh_gitlab_detected(self):
        assert detect_provider("git@gitlab.com:owner/repo.git").value == "gitlab"


# ---------------------------------------------------------------------------
# CLI repo add: provider auto-detection
# ---------------------------------------------------------------------------


class TestRepoAddProviderDetection:
    """Test that repo add stores the detected provider."""

    def test_repo_add_github_provider(self, tmp_project):
        """Adding a GitHub repo should store provider='github'."""
        from typer.testing import CliRunner

        from code_adapt.cli.main import app

        runner = CliRunner()
        # Patch _detect_remote_branch to avoid actual git ls-remote
        with patch("code_adapt.cli.main._detect_remote_branch", return_value="main"):
            result = runner.invoke(app, ["repo", "add", "upstream", "myrepo", "https://github.com/owner/repo"])

        assert result.exit_code == 0, result.output
        # Verify stored data
        repos_data = yaml.safe_load((tmp_project / ".adapt" / "repos.yaml").read_text())
        assert len(repos_data) == 1
        assert repos_data[0]["provider"] == "github"

    def test_repo_add_gitlab_provider(self, tmp_project):
        """Adding a GitLab repo should store provider='gitlab'."""
        from typer.testing import CliRunner

        from code_adapt.cli.main import app

        runner = CliRunner()
        with patch("code_adapt.cli.main._detect_remote_branch", return_value="main"):
            result = runner.invoke(app, ["repo", "add", "upstream", "glrepo", "https://gitlab.com/owner/repo"])

        assert result.exit_code == 0, result.output
        repos_data = yaml.safe_load((tmp_project / ".adapt" / "repos.yaml").read_text())
        assert len(repos_data) == 1
        assert repos_data[0]["provider"] == "gitlab"

    def test_repo_add_gitcode_provider(self, tmp_project):
        """Adding a gitcode.com repo should store provider='gitcode'."""
        from typer.testing import CliRunner

        from code_adapt.cli.main import app

        runner = CliRunner()
        with patch("code_adapt.cli.main._detect_remote_branch", return_value="main"):
            result = runner.invoke(app, ["repo", "add", "upstream", "gcrepo", "https://gitcode.com/owner/repo"])

        assert result.exit_code == 0, result.output
        repos_data = yaml.safe_load((tmp_project / ".adapt" / "repos.yaml").read_text())
        assert len(repos_data) == 1
        assert repos_data[0]["provider"] == "gitcode"

    def test_repo_add_downstream_dot_gets_unknown(self, tmp_project):
        """Adding a downstream repo with url='.' should store provider='unknown'."""
        from typer.testing import CliRunner

        from code_adapt.cli.main import app

        runner = CliRunner()
        with patch("code_adapt.cli.main._detect_local_branch", return_value="main"):
            result = runner.invoke(app, ["repo", "add", "downstream", "local", "."])

        assert result.exit_code == 0, result.output
        repos_data = yaml.safe_load((tmp_project / ".adapt" / "repos.yaml").read_text())
        assert len(repos_data) == 1
        assert repos_data[0]["provider"] == "unknown"

    def test_repo_add_json_output_includes_provider(self, tmp_project):
        """JSON output from repo add should include the provider field."""
        from typer.testing import CliRunner

        from code_adapt.cli.main import app

        runner = CliRunner()
        with patch("code_adapt.cli.main._detect_remote_branch", return_value="main"):
            result = runner.invoke(
                app, ["repo", "add", "upstream", "myrepo", "https://gitlab.com/a/b", "--json"]
            )

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["provider"] == "gitlab"
