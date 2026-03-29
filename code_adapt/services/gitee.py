"""Gitee REST API client via httpx.

Compatible with gitee.com (Gitee API v5).  Gitee's API is similar to GitHub's
but lives at ``/api/v5/`` and authenticates via an ``access_token`` query
parameter rather than an ``Authorization`` header.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from ..models import CommitSummary, PRSummary, ReleaseSummary


class GiteeClient:
    """Thin wrapper around the Gitee v5 REST API.

    Parameters
    ----------
    base_url:
        API base URL, e.g. ``https://gitee.com/api/v5``.
    token:
        Personal access token sent as the ``access_token`` query parameter.
    """

    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url,
            timeout=30.0,
        )

    def _auth_params(self) -> dict[str, str]:
        """Return query parameters for authentication."""
        return {"access_token": self.token}

    # ------------------------------------------------------------------
    # Public API — return types mirror github.py / gitlab.py
    # ------------------------------------------------------------------

    def fetch_commits(
        self, owner: str, repo: str, since: datetime | None = None
    ) -> list[CommitSummary]:
        """GET /repos/{owner}/{repo}/commits"""
        with self._client() as client:
            params: dict = {**self._auth_params(), "per_page": 100}
            if since:
                params["since"] = since.isoformat()
            resp = client.get(f"/repos/{owner}/{repo}/commits", params=params)
            resp.raise_for_status()
            return [
                CommitSummary(
                    sha=c["sha"],
                    message=c["commit"]["message"].split("\n")[0],
                    author=(
                        c["commit"]["author"]["name"]
                        if c.get("commit", {}).get("author")
                        else c.get("author", {}).get("login", "unknown")
                    ),
                    date=(
                        c["commit"]["author"]["date"]
                        if c.get("commit", {}).get("author")
                        else ""
                    ),
                )
                for c in resp.json()
            ]

    def fetch_pull_requests(
        self, owner: str, repo: str, since: datetime | None = None
    ) -> list[PRSummary]:
        """GET /repos/{owner}/{repo}/pulls"""
        with self._client() as client:
            params: dict = {
                **self._auth_params(),
                "state": "all",
                "sort": "updated",
                "direction": "desc",
                "per_page": 100,
            }
            resp = client.get(f"/repos/{owner}/{repo}/pulls", params=params)
            resp.raise_for_status()
            prs = resp.json()
            if since:
                since_ts = since.timestamp()
                prs = [
                    pr
                    for pr in prs
                    if pr.get("updated_at")
                    and datetime.fromisoformat(
                        pr["updated_at"].replace("Z", "+00:00")
                    ).timestamp()
                    >= since_ts
                ]
            return [
                PRSummary(
                    number=pr["number"],
                    title=pr["title"],
                    state=pr["state"],
                    author=pr.get("user", {}).get("login", "unknown"),
                    url=pr.get("html_url", ""),
                )
                for pr in prs
            ]

    def fetch_releases(
        self, owner: str, repo: str, since: datetime | None = None
    ) -> list[ReleaseSummary]:
        """GET /repos/{owner}/{repo}/releases"""
        with self._client() as client:
            params: dict = {**self._auth_params(), "per_page": 100}
            resp = client.get(f"/repos/{owner}/{repo}/releases", params=params)
            resp.raise_for_status()
            releases = resp.json()
            if since:
                since_ts = since.timestamp()
                releases = [
                    r
                    for r in releases
                    if r.get("created_at")
                    and datetime.fromisoformat(
                        r["created_at"].replace("Z", "+00:00")
                    ).timestamp()
                    >= since_ts
                ]
            return [
                ReleaseSummary(
                    tag=r["tag_name"],
                    name=r.get("name") or r["tag_name"],
                    date=r.get("created_at", ""),
                    url=r.get("html_url", ""),
                )
                for r in releases
            ]

    def fetch_pr_diff(
        self, owner: str, repo: str, pr_number: int
    ) -> dict[str, Any]:
        """Return ``{files, additions, deletions, message}`` for a pull request.

        Gitee provides ``/repos/{owner}/{repo}/pulls/{number}/files`` similar
        to GitHub.
        """
        with self._client() as client:
            files_resp = client.get(
                f"/repos/{owner}/{repo}/pulls/{pr_number}/files",
                params={**self._auth_params(), "per_page": 100},
            )
            files_resp.raise_for_status()
            file_data = files_resp.json()

            pr_resp = client.get(
                f"/repos/{owner}/{repo}/pulls/{pr_number}",
                params=self._auth_params(),
            )
            pr_resp.raise_for_status()
            title = pr_resp.json()["title"]

            files = [f["filename"] for f in file_data]
            additions = sum(f.get("additions", 0) for f in file_data)
            deletions = sum(f.get("deletions", 0) for f in file_data)
            return {
                "files": files,
                "additions": additions,
                "deletions": deletions,
                "message": title,
            }

    def fetch_commit_diff(
        self, owner: str, repo: str, sha: str
    ) -> dict[str, Any]:
        """Return ``{files, additions, deletions, message}`` for a commit.

        GET /repos/{owner}/{repo}/commits/{sha}
        """
        with self._client() as client:
            resp = client.get(
                f"/repos/{owner}/{repo}/commits/{sha}",
                params=self._auth_params(),
            )
            resp.raise_for_status()
            data = resp.json()
            commit_files = data.get("files", [])
            return {
                "files": [f["filename"] for f in commit_files],
                "additions": sum(f.get("additions", 0) for f in commit_files),
                "deletions": sum(f.get("deletions", 0) for f in commit_files),
                "message": data.get("commit", {}).get("message", ""),
            }
