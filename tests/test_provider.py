"""Tests for the multi-provider abstraction layer."""

from __future__ import annotations

import pytest

from code_adapt.errors import ValidationError
from code_adapt.services.provider import (
    Provider,
    api_base_url,
    detect_provider,
    parse_repo_url,
)


# ---------------------------------------------------------------------------
# detect_provider
# ---------------------------------------------------------------------------


class TestDetectProvider:
    """Provider detection from HTTPS and SSH URLs."""

    # -- GitHub --

    def test_github_https(self):
        assert detect_provider("https://github.com/owner/repo") == Provider.GITHUB

    def test_github_https_git_suffix(self):
        assert detect_provider("https://github.com/owner/repo.git") == Provider.GITHUB

    def test_github_ssh(self):
        assert detect_provider("git@github.com:owner/repo.git") == Provider.GITHUB

    def test_github_ssh_no_suffix(self):
        assert detect_provider("git@github.com:owner/repo") == Provider.GITHUB

    # -- GitLab --

    def test_gitlab_https(self):
        assert detect_provider("https://gitlab.com/owner/repo") == Provider.GITLAB

    def test_gitlab_ssh(self):
        assert detect_provider("git@gitlab.com:owner/repo.git") == Provider.GITLAB

    # -- gitcode --

    def test_gitcode_com_https(self):
        assert detect_provider("https://gitcode.com/owner/repo") == Provider.GITCODE

    def test_gitcode_net_https(self):
        assert detect_provider("https://gitcode.net/owner/repo") == Provider.GITCODE

    def test_gitcode_ssh(self):
        assert detect_provider("git@gitcode.com:owner/repo.git") == Provider.GITCODE

    # -- Gitea --

    def test_gitea_com_https(self):
        assert detect_provider("https://gitea.com/owner/repo") == Provider.GITEA

    def test_codeberg_https(self):
        assert detect_provider("https://codeberg.org/owner/repo") == Provider.GITEA

    def test_codeberg_ssh(self):
        assert detect_provider("git@codeberg.org:owner/repo.git") == Provider.GITEA

    # -- Unknown / self-hosted --

    def test_unknown_self_hosted(self):
        assert detect_provider("https://git.example.com/owner/repo") == Provider.UNKNOWN

    def test_unknown_custom_domain(self):
        assert detect_provider("https://my-gitea.internal.io/org/project") == Provider.UNKNOWN

    def test_unknown_ssh(self):
        assert detect_provider("git@custom-host.local:team/project.git") == Provider.UNKNOWN


# ---------------------------------------------------------------------------
# parse_repo_url
# ---------------------------------------------------------------------------


class TestParseRepoUrl:
    """Owner/repo extraction from various URL formats."""

    # -- GitHub HTTPS --

    def test_github_https(self):
        assert parse_repo_url("https://github.com/torvalds/linux") == ("torvalds", "linux")

    def test_github_https_git_suffix(self):
        assert parse_repo_url("https://github.com/torvalds/linux.git") == ("torvalds", "linux")

    def test_github_https_trailing_slash(self):
        assert parse_repo_url("https://github.com/torvalds/linux/") == ("torvalds", "linux")

    # -- GitHub SSH --

    def test_github_ssh(self):
        assert parse_repo_url("git@github.com:torvalds/linux.git") == ("torvalds", "linux")

    def test_github_ssh_no_suffix(self):
        assert parse_repo_url("git@github.com:torvalds/linux") == ("torvalds", "linux")

    # -- GitLab --

    def test_gitlab_https(self):
        assert parse_repo_url("https://gitlab.com/inkscape/inkscape") == ("inkscape", "inkscape")

    def test_gitlab_ssh(self):
        assert parse_repo_url("git@gitlab.com:inkscape/inkscape.git") == ("inkscape", "inkscape")

    def test_gitlab_ssh_protocol(self):
        assert parse_repo_url("ssh://git@gitlab.com/inkscape/inkscape.git") == (
            "inkscape",
            "inkscape",
        )

    # -- gitcode --

    def test_gitcode_https(self):
        assert parse_repo_url("https://gitcode.com/openJiuwen/agent") == ("openJiuwen", "agent")

    def test_gitcode_net(self):
        assert parse_repo_url("https://gitcode.net/openJiuwen/agent.git") == (
            "openJiuwen",
            "agent",
        )

    def test_gitcode_ssh(self):
        assert parse_repo_url("git@gitcode.com:openJiuwen/agent.git") == ("openJiuwen", "agent")

    # -- Gitea / Codeberg --

    def test_gitea_https(self):
        assert parse_repo_url("https://gitea.com/gitea/tea") == ("gitea", "tea")

    def test_codeberg_https(self):
        assert parse_repo_url("https://codeberg.org/forgejo/forgejo") == ("forgejo", "forgejo")

    def test_codeberg_ssh(self):
        assert parse_repo_url("git@codeberg.org:forgejo/forgejo.git") == ("forgejo", "forgejo")

    # -- Self-hosted --

    def test_self_hosted_https(self):
        assert parse_repo_url("https://git.example.com/team/project") == ("team", "project")

    def test_self_hosted_ssh(self):
        assert parse_repo_url("git@git.internal.io:team/project.git") == ("team", "project")

    # -- Edge cases --

    def test_hyphenated_names(self):
        assert parse_repo_url("https://github.com/my-org/my-repo") == ("my-org", "my-repo")

    def test_underscored_names(self):
        assert parse_repo_url("https://github.com/my_org/my_repo") == ("my_org", "my_repo")

    def test_dotted_owner(self):
        assert parse_repo_url("https://github.com/a.b/c") == ("a.b", "c")

    def test_invalid_url_raises(self):
        with pytest.raises(ValidationError, match="Cannot parse owner/repo"):
            parse_repo_url("not-a-url")

    def test_bare_domain_raises(self):
        with pytest.raises(ValidationError, match="Cannot parse owner/repo"):
            parse_repo_url("https://github.com/")

    def test_single_segment_raises(self):
        with pytest.raises(ValidationError, match="Cannot parse owner/repo"):
            parse_repo_url("https://github.com/owner")


# ---------------------------------------------------------------------------
# api_base_url
# ---------------------------------------------------------------------------


class TestApiBaseUrl:
    """API base URL resolution for cloud and self-hosted providers."""

    # -- Cloud defaults (no URL needed) --

    def test_github_cloud(self):
        assert api_base_url(Provider.GITHUB) == "https://api.github.com"

    def test_gitlab_cloud(self):
        assert api_base_url(Provider.GITLAB) == "https://gitlab.com/api/v4"

    def test_gitcode_cloud(self):
        assert api_base_url(Provider.GITCODE) == "https://gitcode.com/api/v4"

    def test_gitea_cloud(self):
        assert api_base_url(Provider.GITEA) == "https://gitea.com/api/v1"

    # -- Cloud with URL (should still return canonical) --

    def test_github_with_url(self):
        assert api_base_url(Provider.GITHUB, "https://github.com/owner/repo") == (
            "https://api.github.com"
        )

    def test_gitlab_with_url(self):
        assert api_base_url(Provider.GITLAB, "https://gitlab.com/owner/repo") == (
            "https://gitlab.com/api/v4"
        )

    # -- Self-hosted --

    def test_self_hosted_gitlab(self):
        url = "https://gitlab.mycompany.com/team/repo"
        assert api_base_url(Provider.GITLAB, url) == "https://gitlab.mycompany.com/api/v4"

    def test_self_hosted_gitea(self):
        url = "https://gitea.internal.io/org/project"
        assert api_base_url(Provider.GITEA, url) == "https://gitea.internal.io/api/v1"

    def test_self_hosted_unknown(self):
        url = "https://git.example.com/org/project"
        assert api_base_url(Provider.UNKNOWN, url) == "https://git.example.com"

    def test_self_hosted_ssh_strips_user(self):
        url = "git@gitlab.mycompany.com:team/repo.git"
        result = api_base_url(Provider.GITLAB, url)
        assert result == "ssh://gitlab.mycompany.com/api/v4"

    # -- Error case --

    def test_unknown_without_url_raises(self):
        with pytest.raises(ValidationError, match="Cannot determine API base URL"):
            api_base_url(Provider.UNKNOWN)


# ---------------------------------------------------------------------------
# Provider enum
# ---------------------------------------------------------------------------


class TestProviderEnum:
    """Basic enum properties."""

    def test_str_values(self):
        assert Provider.GITHUB.value == "github"
        assert Provider.GITLAB.value == "gitlab"
        assert Provider.GITEA.value == "gitea"
        assert Provider.GITCODE.value == "gitcode"
        assert Provider.UNKNOWN.value == "unknown"

    def test_is_str_enum(self):
        assert isinstance(Provider.GITHUB, str)
        assert Provider.GITHUB == "github"
