"""Tests for the Gitee API client."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import httpx
import pytest

from code_adapt.errors import AuthError
from code_adapt.services.auth import get_token
from code_adapt.services.gitee import GiteeClient
from code_adapt.services.provider import Provider, api_base_url, detect_provider


# ---------------------------------------------------------------------------
# GiteeClient — initialisation
# ---------------------------------------------------------------------------


class TestGiteeClientInit:
    """Constructor and basic configuration."""

    def test_stores_base_url(self):
        client = GiteeClient("https://gitee.com/api/v5", "tok")
        assert client.base_url == "https://gitee.com/api/v5"

    def test_strips_trailing_slash_from_base_url(self):
        client = GiteeClient("https://gitee.com/api/v5/", "tok")
        assert client.base_url == "https://gitee.com/api/v5"

    def test_stores_token(self):
        client = GiteeClient("https://gitee.com/api/v5", "gitee-abc123")
        assert client.token == "gitee-abc123"


# ---------------------------------------------------------------------------
# GiteeClient — auth token passing
# ---------------------------------------------------------------------------


class TestGiteeClientAuth:
    """Authentication via access_token query parameter."""

    def test_auth_params_contain_access_token(self):
        client = GiteeClient("https://gitee.com/api/v5", "my-token")
        params = client._auth_params()
        assert params == {"access_token": "my-token"}

    def test_auth_token_sent_as_query_param(self):
        """Verify that the access_token is included in the request URL."""
        api_response = []
        captured_requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_requests.append(request)
            return httpx.Response(200, json=api_response)

        transport = httpx.MockTransport(handler)
        client = GiteeClient("https://gitee.com/api/v5", "secret-tok")
        with patch.object(client, "_client") as mock_client:
            mock_client.return_value = httpx.Client(
                base_url="https://gitee.com/api/v5",
                transport=transport,
            )
            client.fetch_commits("owner", "repo")

        assert len(captured_requests) == 1
        assert "access_token=secret-tok" in str(captured_requests[0].url)


# ---------------------------------------------------------------------------
# GiteeClient — fetch_commits
# ---------------------------------------------------------------------------


class TestGiteeClientFetchCommits:
    """Commit listing via the Gitee API."""

    def test_fetch_commits_returns_commit_summaries(self):
        api_response = [
            {
                "sha": "abc123",
                "commit": {
                    "message": "Fix bug in parser\n\nDetailed description",
                    "author": {"name": "Alice", "date": "2025-01-15T10:00:00Z"},
                },
                "author": {"login": "alice"},
            },
            {
                "sha": "def456",
                "commit": {
                    "message": "Add feature X",
                    "author": {"name": "Bob", "date": "2025-01-16T12:00:00Z"},
                },
                "author": {"login": "bob"},
            },
        ]
        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json=api_response)
        )
        client = GiteeClient("https://gitee.com/api/v5", "tok")
        with patch.object(client, "_client") as mock_client:
            mock_client.return_value = httpx.Client(
                base_url="https://gitee.com/api/v5",
                transport=transport,
            )
            commits = client.fetch_commits("owner", "repo")

        assert len(commits) == 2
        assert commits[0].sha == "abc123"
        assert commits[0].message == "Fix bug in parser"
        assert commits[0].author == "Alice"
        assert commits[0].date == "2025-01-15T10:00:00Z"
        assert commits[1].sha == "def456"
        assert commits[1].message == "Add feature X"

    def test_fetch_commits_handles_missing_author(self):
        api_response = [
            {
                "sha": "abc123",
                "commit": {
                    "message": "Automated commit",
                    "author": None,
                },
                "author": {"login": "bot"},
            },
        ]
        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json=api_response)
        )
        client = GiteeClient("https://gitee.com/api/v5", "tok")
        with patch.object(client, "_client") as mock_client:
            mock_client.return_value = httpx.Client(
                base_url="https://gitee.com/api/v5",
                transport=transport,
            )
            commits = client.fetch_commits("owner", "repo")

        assert commits[0].author == "bot"

    def test_fetch_commits_with_since(self):
        """Verify 'since' param is passed in the request."""
        captured_requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_requests.append(request)
            return httpx.Response(200, json=[])

        transport = httpx.MockTransport(handler)
        client = GiteeClient("https://gitee.com/api/v5", "tok")
        with patch.object(client, "_client") as mock_client:
            mock_client.return_value = httpx.Client(
                base_url="https://gitee.com/api/v5",
                transport=transport,
            )
            since = datetime(2025, 1, 1, tzinfo=timezone.utc)
            client.fetch_commits("owner", "repo", since=since)

        assert len(captured_requests) == 1
        assert "since=" in str(captured_requests[0].url)


# ---------------------------------------------------------------------------
# GiteeClient — fetch_pull_requests
# ---------------------------------------------------------------------------


class TestGiteeClientFetchPullRequests:
    """Pull request listing via the Gitee API."""

    def test_fetch_pull_requests_returns_pr_summaries(self):
        api_response = [
            {
                "number": 42,
                "title": "Add dark mode",
                "state": "merged",
                "user": {"login": "alice"},
                "html_url": "https://gitee.com/owner/repo/pulls/42",
                "updated_at": "2025-03-01T00:00:00Z",
            },
            {
                "number": 43,
                "title": "Fix typo",
                "state": "open",
                "user": {"login": "bob"},
                "html_url": "https://gitee.com/owner/repo/pulls/43",
                "updated_at": "2025-03-02T00:00:00Z",
            },
        ]
        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json=api_response)
        )
        client = GiteeClient("https://gitee.com/api/v5", "tok")
        with patch.object(client, "_client") as mock_client:
            mock_client.return_value = httpx.Client(
                base_url="https://gitee.com/api/v5",
                transport=transport,
            )
            prs = client.fetch_pull_requests("owner", "repo")

        assert len(prs) == 2
        assert prs[0].number == 42
        assert prs[0].title == "Add dark mode"
        assert prs[0].state == "merged"
        assert prs[0].author == "alice"
        assert prs[0].url == "https://gitee.com/owner/repo/pulls/42"

    def test_fetch_pull_requests_filters_by_since(self):
        api_response = [
            {
                "number": 42,
                "title": "Old PR",
                "state": "merged",
                "user": {"login": "alice"},
                "html_url": "https://gitee.com/owner/repo/pulls/42",
                "updated_at": "2024-01-01T00:00:00Z",
            },
            {
                "number": 43,
                "title": "New PR",
                "state": "open",
                "user": {"login": "bob"},
                "html_url": "https://gitee.com/owner/repo/pulls/43",
                "updated_at": "2025-06-01T00:00:00Z",
            },
        ]
        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json=api_response)
        )
        client = GiteeClient("https://gitee.com/api/v5", "tok")
        with patch.object(client, "_client") as mock_client:
            mock_client.return_value = httpx.Client(
                base_url="https://gitee.com/api/v5",
                transport=transport,
            )
            since = datetime(2025, 1, 1, tzinfo=timezone.utc)
            prs = client.fetch_pull_requests("owner", "repo", since=since)

        assert len(prs) == 1
        assert prs[0].number == 43

    def test_fetch_pull_requests_handles_missing_user(self):
        api_response = [
            {
                "number": 1,
                "title": "Bot PR",
                "state": "open",
                "html_url": "https://gitee.com/owner/repo/pulls/1",
                "updated_at": "2025-03-01T00:00:00Z",
            },
        ]
        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json=api_response)
        )
        client = GiteeClient("https://gitee.com/api/v5", "tok")
        with patch.object(client, "_client") as mock_client:
            mock_client.return_value = httpx.Client(
                base_url="https://gitee.com/api/v5",
                transport=transport,
            )
            prs = client.fetch_pull_requests("owner", "repo")

        assert prs[0].author == "unknown"


# ---------------------------------------------------------------------------
# GiteeClient — fetch_releases
# ---------------------------------------------------------------------------


class TestGiteeClientFetchReleases:
    """Release listing via the Gitee API."""

    def test_fetch_releases_returns_release_summaries(self):
        api_response = [
            {
                "tag_name": "v1.0.0",
                "name": "Version 1.0",
                "created_at": "2025-03-01T00:00:00Z",
                "html_url": "https://gitee.com/owner/repo/releases/v1.0.0",
            },
            {
                "tag_name": "v0.9.0",
                "name": "Version 0.9",
                "created_at": "2025-02-01T00:00:00Z",
                "html_url": "https://gitee.com/owner/repo/releases/v0.9.0",
            },
        ]
        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json=api_response)
        )
        client = GiteeClient("https://gitee.com/api/v5", "tok")
        with patch.object(client, "_client") as mock_client:
            mock_client.return_value = httpx.Client(
                base_url="https://gitee.com/api/v5",
                transport=transport,
            )
            releases = client.fetch_releases("owner", "repo")

        assert len(releases) == 2
        assert releases[0].tag == "v1.0.0"
        assert releases[0].name == "Version 1.0"
        assert releases[0].date == "2025-03-01T00:00:00Z"
        assert releases[0].url == "https://gitee.com/owner/repo/releases/v1.0.0"

    def test_fetch_releases_filters_by_since(self):
        api_response = [
            {
                "tag_name": "v2.0.0",
                "name": "Version 2.0",
                "created_at": "2025-06-01T00:00:00Z",
                "html_url": "https://gitee.com/owner/repo/releases/v2.0.0",
            },
            {
                "tag_name": "v1.0.0",
                "name": "Version 1.0",
                "created_at": "2024-01-01T00:00:00Z",
                "html_url": "https://gitee.com/owner/repo/releases/v1.0.0",
            },
        ]
        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json=api_response)
        )
        client = GiteeClient("https://gitee.com/api/v5", "tok")
        with patch.object(client, "_client") as mock_client:
            mock_client.return_value = httpx.Client(
                base_url="https://gitee.com/api/v5",
                transport=transport,
            )
            since = datetime(2025, 1, 1, tzinfo=timezone.utc)
            releases = client.fetch_releases("owner", "repo", since=since)

        assert len(releases) == 1
        assert releases[0].tag == "v2.0.0"

    def test_fetch_releases_uses_tag_name_when_name_missing(self):
        api_response = [
            {
                "tag_name": "v3.0.0",
                "name": None,
                "created_at": "2025-03-01T00:00:00Z",
                "html_url": "https://gitee.com/owner/repo/releases/v3.0.0",
            },
        ]
        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json=api_response)
        )
        client = GiteeClient("https://gitee.com/api/v5", "tok")
        with patch.object(client, "_client") as mock_client:
            mock_client.return_value = httpx.Client(
                base_url="https://gitee.com/api/v5",
                transport=transport,
            )
            releases = client.fetch_releases("owner", "repo")

        assert releases[0].name == "v3.0.0"


# ---------------------------------------------------------------------------
# GiteeClient — fetch_pr_diff
# ---------------------------------------------------------------------------


class TestGiteeClientFetchPrDiff:
    """PR diff retrieval."""

    def test_fetch_pr_diff_parses_files(self):
        files_response = [
            {"filename": "src/main.py", "additions": 10, "deletions": 3},
            {"filename": "README.md", "additions": 5, "deletions": 0},
        ]
        pr_response = {"title": "Add feature"}

        def handler(request: httpx.Request) -> httpx.Response:
            if "files" in str(request.url):
                return httpx.Response(200, json=files_response)
            return httpx.Response(200, json=pr_response)

        transport = httpx.MockTransport(handler)
        client = GiteeClient("https://gitee.com/api/v5", "tok")
        with patch.object(client, "_client") as mock_client:
            mock_client.return_value = httpx.Client(
                base_url="https://gitee.com/api/v5",
                transport=transport,
            )
            diff = client.fetch_pr_diff("owner", "repo", 42)

        assert diff["files"] == ["src/main.py", "README.md"]
        assert diff["additions"] == 15
        assert diff["deletions"] == 3
        assert diff["message"] == "Add feature"


# ---------------------------------------------------------------------------
# GiteeClient — fetch_commit_diff
# ---------------------------------------------------------------------------


class TestGiteeClientFetchCommitDiff:
    """Commit diff retrieval."""

    def test_fetch_commit_diff_parses_response(self):
        api_response = {
            "commit": {"message": "Fix null pointer\n\nDetailed description"},
            "files": [
                {"filename": "lib/parser.py", "additions": 5, "deletions": 2},
                {"filename": "tests/test_parser.py", "additions": 10, "deletions": 0},
            ],
        }
        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json=api_response)
        )
        client = GiteeClient("https://gitee.com/api/v5", "tok")
        with patch.object(client, "_client") as mock_client:
            mock_client.return_value = httpx.Client(
                base_url="https://gitee.com/api/v5",
                transport=transport,
            )
            diff = client.fetch_commit_diff("owner", "repo", "abc123")

        assert diff["files"] == ["lib/parser.py", "tests/test_parser.py"]
        assert diff["additions"] == 15
        assert diff["deletions"] == 2
        assert diff["message"] == "Fix null pointer\n\nDetailed description"


# ---------------------------------------------------------------------------
# GiteeClient — error handling
# ---------------------------------------------------------------------------


class TestGiteeClientErrorHandling:
    """HTTP error responses raise exceptions."""

    def test_fetch_commits_raises_on_401(self):
        transport = httpx.MockTransport(
            lambda req: httpx.Response(401, json={"message": "Unauthorized"})
        )
        client = GiteeClient("https://gitee.com/api/v5", "bad-token")
        with patch.object(client, "_client") as mock_client:
            mock_client.return_value = httpx.Client(
                base_url="https://gitee.com/api/v5",
                transport=transport,
            )
            with pytest.raises(httpx.HTTPStatusError):
                client.fetch_commits("owner", "repo")

    def test_fetch_pull_requests_raises_on_404(self):
        transport = httpx.MockTransport(
            lambda req: httpx.Response(404, json={"message": "Not Found"})
        )
        client = GiteeClient("https://gitee.com/api/v5", "tok")
        with patch.object(client, "_client") as mock_client:
            mock_client.return_value = httpx.Client(
                base_url="https://gitee.com/api/v5",
                transport=transport,
            )
            with pytest.raises(httpx.HTTPStatusError):
                client.fetch_pull_requests("owner", "repo")

    def test_fetch_releases_raises_on_500(self):
        transport = httpx.MockTransport(
            lambda req: httpx.Response(500, json={"message": "Internal Server Error"})
        )
        client = GiteeClient("https://gitee.com/api/v5", "tok")
        with patch.object(client, "_client") as mock_client:
            mock_client.return_value = httpx.Client(
                base_url="https://gitee.com/api/v5",
                transport=transport,
            )
            with pytest.raises(httpx.HTTPStatusError):
                client.fetch_releases("owner", "repo")


# ---------------------------------------------------------------------------
# Provider detection and token resolution for Gitee
# ---------------------------------------------------------------------------


class TestGiteeProviderIntegration:
    """Provider detection, API base URL, and token resolution for Gitee."""

    def test_detect_gitee_https(self):
        assert detect_provider("https://gitee.com/owner/repo") == Provider.GITEE

    def test_detect_gitee_ssh(self):
        assert detect_provider("git@gitee.com:owner/repo.git") == Provider.GITEE

    def test_gitee_api_base_url_cloud(self):
        assert api_base_url(Provider.GITEE) == "https://gitee.com/api/v5"

    def test_gitee_api_base_url_with_url(self):
        assert api_base_url(Provider.GITEE, "https://gitee.com/owner/repo") == (
            "https://gitee.com/api/v5"
        )

    def test_gitee_enum_value(self):
        assert Provider.GITEE.value == "gitee"
        assert isinstance(Provider.GITEE, str)

    def test_gitee_token_via_env_var(self):
        with patch.dict("os.environ", {"GITEE_TOKEN": "gitee-tok"}):
            token = get_token(Provider.GITEE)
        assert token == "gitee-tok"

    def test_gitee_raises_when_no_token(self):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(AuthError, match="No gitee token found"):
                get_token(Provider.GITEE)
