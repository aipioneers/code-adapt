"""Tests for the GitLab API client and multi-provider token resolution."""

from __future__ import annotations

import json
from unittest.mock import patch

import httpx
import pytest

from code_adapt.errors import AuthError
from code_adapt.services.auth import get_github_token, get_token
from code_adapt.services.gitlab import GitLabClient
from code_adapt.services.provider import Provider


# ---------------------------------------------------------------------------
# GitLabClient — initialisation
# ---------------------------------------------------------------------------


class TestGitLabClientInit:
    """Constructor and basic configuration."""

    def test_stores_base_url(self):
        client = GitLabClient("https://gitlab.com/api/v4", "tok")
        assert client.base_url == "https://gitlab.com/api/v4"

    def test_strips_trailing_slash_from_base_url(self):
        client = GitLabClient("https://gitlab.com/api/v4/", "tok")
        assert client.base_url == "https://gitlab.com/api/v4"

    def test_stores_token(self):
        client = GitLabClient("https://gitlab.com/api/v4", "glpat-abc123")
        assert client.token == "glpat-abc123"


# ---------------------------------------------------------------------------
# GitLabClient — headers
# ---------------------------------------------------------------------------


class TestGitLabClientHeaders:
    """Authentication header generation."""

    def test_headers_contain_private_token(self):
        client = GitLabClient("https://gitlab.com/api/v4", "my-token")
        headers = client._headers()
        assert headers == {"PRIVATE-TOKEN": "my-token"}

    def test_headers_use_correct_token_value(self):
        client = GitLabClient("https://gitlab.com/api/v4", "glpat-xyz789")
        assert client._headers()["PRIVATE-TOKEN"] == "glpat-xyz789"


# ---------------------------------------------------------------------------
# GitLabClient — project path encoding
# ---------------------------------------------------------------------------


class TestGitLabClientProjectPath:
    """URL encoding of owner/repo for /projects/:id endpoints."""

    def test_encodes_slash(self):
        assert GitLabClient._project_path("owner", "repo") == "owner%2Frepo"

    def test_preserves_hyphens(self):
        assert GitLabClient._project_path("my-org", "my-repo") == "my-org%2Fmy-repo"

    def test_preserves_underscores(self):
        assert GitLabClient._project_path("my_org", "my_repo") == "my_org%2Fmy_repo"

    def test_encodes_dots(self):
        # Dots are allowed by default in URL path segments; quote() keeps them.
        path = GitLabClient._project_path("a.b", "c.d")
        assert path == "a.b%2Fc.d"

    def test_encodes_special_characters(self):
        path = GitLabClient._project_path("org", "repo with spaces")
        assert "%2F" in path
        assert "%20" in path or "+" in path  # space encoding


# ---------------------------------------------------------------------------
# GitLabClient — fetch_commits
# ---------------------------------------------------------------------------


class TestGitLabClientFetchCommits:
    """Commit listing via the GitLab API."""

    def test_fetch_commits_returns_commit_summaries(self):
        api_response = [
            {
                "id": "abc123",
                "title": "Fix bug in parser",
                "author_name": "Alice",
                "committed_date": "2025-01-15T10:00:00Z",
            },
            {
                "id": "def456",
                "title": "Add feature X",
                "author_name": "Bob",
                "committed_date": "2025-01-16T12:00:00Z",
            },
        ]
        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json=api_response)
        )
        client = GitLabClient("https://gitlab.com/api/v4", "tok")
        with patch.object(client, "_client") as mock_client:
            mock_client.return_value = httpx.Client(
                base_url="https://gitlab.com/api/v4",
                transport=transport,
            )
            commits = client.fetch_commits("owner", "repo")

        assert len(commits) == 2
        assert commits[0].sha == "abc123"
        assert commits[0].message == "Fix bug in parser"
        assert commits[0].author == "Alice"
        assert commits[1].sha == "def456"

    def test_fetch_commits_handles_missing_author(self):
        api_response = [
            {
                "id": "abc123",
                "title": "Automated commit",
                "committed_date": "2025-01-15T10:00:00Z",
            },
        ]
        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json=api_response)
        )
        client = GitLabClient("https://gitlab.com/api/v4", "tok")
        with patch.object(client, "_client") as mock_client:
            mock_client.return_value = httpx.Client(
                base_url="https://gitlab.com/api/v4",
                transport=transport,
            )
            commits = client.fetch_commits("owner", "repo")

        assert commits[0].author == "unknown"


# ---------------------------------------------------------------------------
# GitLabClient — fetch_merge_requests
# ---------------------------------------------------------------------------


class TestGitLabClientFetchMergeRequests:
    """Merge request listing via the GitLab API."""

    def test_fetch_merge_requests_returns_pr_summaries(self):
        api_response = [
            {
                "iid": 42,
                "title": "Add dark mode",
                "state": "merged",
                "author": {"username": "alice"},
                "web_url": "https://gitlab.com/owner/repo/-/merge_requests/42",
            },
        ]
        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json=api_response)
        )
        client = GitLabClient("https://gitlab.com/api/v4", "tok")
        with patch.object(client, "_client") as mock_client:
            mock_client.return_value = httpx.Client(
                base_url="https://gitlab.com/api/v4",
                transport=transport,
            )
            mrs = client.fetch_merge_requests("owner", "repo")

        assert len(mrs) == 1
        assert mrs[0].number == 42
        assert mrs[0].title == "Add dark mode"
        assert mrs[0].state == "merged"
        assert mrs[0].author == "alice"
        assert mrs[0].url == "https://gitlab.com/owner/repo/-/merge_requests/42"


# ---------------------------------------------------------------------------
# GitLabClient — fetch_mr_diff
# ---------------------------------------------------------------------------


class TestGitLabClientFetchMrDiff:
    """MR diff retrieval."""

    def test_fetch_mr_diff_parses_changes(self):
        api_response = {
            "title": "Add feature",
            "changes": [
                {
                    "new_path": "src/main.py",
                    "old_path": "src/main.py",
                    "diff": "+added line 1\n+added line 2\n-removed line\n context",
                },
                {
                    "new_path": "README.md",
                    "old_path": "README.md",
                    "diff": "+new doc line\n",
                },
            ],
        }
        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json=api_response)
        )
        client = GitLabClient("https://gitlab.com/api/v4", "tok")
        with patch.object(client, "_client") as mock_client:
            mock_client.return_value = httpx.Client(
                base_url="https://gitlab.com/api/v4",
                transport=transport,
            )
            diff = client.fetch_mr_diff("owner", "repo", 42)

        assert diff["files"] == ["src/main.py", "README.md"]
        assert diff["additions"] == 3
        assert diff["deletions"] == 1
        assert diff["message"] == "Add feature"


# ---------------------------------------------------------------------------
# GitLabClient — fetch_commit_diff
# ---------------------------------------------------------------------------


class TestGitLabClientFetchCommitDiff:
    """Commit diff retrieval."""

    def test_fetch_commit_diff_parses_diffs(self):
        commit_response = {"message": "Fix null pointer\n\nDetailed description"}
        diff_response = [
            {
                "new_path": "lib/parser.py",
                "old_path": "lib/parser.py",
                "diff": "+fix\n-bug\n",
            },
        ]

        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if "diff" in str(request.url):
                return httpx.Response(200, json=diff_response)
            return httpx.Response(200, json=commit_response)

        transport = httpx.MockTransport(handler)
        client = GitLabClient("https://gitlab.com/api/v4", "tok")
        with patch.object(client, "_client") as mock_client:
            mock_client.return_value = httpx.Client(
                base_url="https://gitlab.com/api/v4",
                transport=transport,
            )
            diff = client.fetch_commit_diff("owner", "repo", "abc123")

        assert diff["files"] == ["lib/parser.py"]
        assert diff["additions"] == 1
        assert diff["deletions"] == 1
        assert diff["message"] == "Fix null pointer\n\nDetailed description"


# ---------------------------------------------------------------------------
# GitLabClient — fetch_releases
# ---------------------------------------------------------------------------


class TestGitLabClientFetchReleases:
    """Release listing via the GitLab API."""

    def test_fetch_releases_returns_release_summaries(self):
        api_response = [
            {
                "tag_name": "v1.0.0",
                "name": "Version 1.0",
                "released_at": "2025-03-01T00:00:00Z",
                "_links": {"self": "https://gitlab.com/api/v4/projects/1/releases/v1.0.0"},
            },
        ]
        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json=api_response)
        )
        client = GitLabClient("https://gitlab.com/api/v4", "tok")
        with patch.object(client, "_client") as mock_client:
            mock_client.return_value = httpx.Client(
                base_url="https://gitlab.com/api/v4",
                transport=transport,
            )
            releases = client.fetch_releases("owner", "repo")

        assert len(releases) == 1
        assert releases[0].tag == "v1.0.0"
        assert releases[0].name == "Version 1.0"
        assert releases[0].date == "2025-03-01T00:00:00Z"


# ---------------------------------------------------------------------------
# Multi-provider token resolution
# ---------------------------------------------------------------------------


class TestGetToken:
    """Token resolution via get_token() for all providers."""

    # -- GitHub --

    def test_github_via_gh_cli(self):
        with patch("code_adapt.services.auth._try_gh_cli", return_value="gh-cli-token"):
            token = get_token(Provider.GITHUB)
        assert token == "gh-cli-token"

    def test_github_via_env_var(self):
        with (
            patch("code_adapt.services.auth._try_gh_cli", return_value=None),
            patch.dict("os.environ", {"GITHUB_TOKEN": "env-token"}),
        ):
            token = get_token(Provider.GITHUB)
        assert token == "env-token"

    def test_github_raises_when_no_token(self):
        with (
            patch("code_adapt.services.auth._try_gh_cli", return_value=None),
            patch.dict("os.environ", {}, clear=True),
        ):
            with pytest.raises(AuthError, match="No github token found"):
                get_token(Provider.GITHUB)

    # -- GitLab --

    def test_gitlab_via_env_var(self):
        with patch.dict("os.environ", {"GITLAB_TOKEN": "glpat-abc"}):
            token = get_token(Provider.GITLAB)
        assert token == "glpat-abc"

    def test_gitlab_raises_when_no_token(self):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(AuthError, match="No gitlab token found"):
                get_token(Provider.GITLAB)

    # -- gitcode --

    def test_gitcode_via_env_var(self):
        with patch.dict("os.environ", {"GITCODE_TOKEN": "gc-token"}):
            token = get_token(Provider.GITCODE)
        assert token == "gc-token"

    def test_gitcode_raises_when_no_token(self):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(AuthError, match="No gitcode token found"):
                get_token(Provider.GITCODE)

    # -- Gitea --

    def test_gitea_via_env_var(self):
        with patch.dict("os.environ", {"GITEA_TOKEN": "gitea-tok"}):
            token = get_token(Provider.GITEA)
        assert token == "gitea-tok"

    def test_gitea_raises_when_no_token(self):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(AuthError, match="No gitea token found"):
                get_token(Provider.GITEA)


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------


class TestGetGitHubTokenBackcompat:
    """get_github_token() still works and delegates to get_token()."""

    def test_delegates_to_get_token(self):
        with patch("code_adapt.services.auth._try_gh_cli", return_value="compat-tok"):
            token = get_github_token()
        assert token == "compat-tok"

    def test_raises_auth_error_on_failure(self):
        with (
            patch("code_adapt.services.auth._try_gh_cli", return_value=None),
            patch.dict("os.environ", {}, clear=True),
        ):
            with pytest.raises(AuthError):
                get_github_token()
