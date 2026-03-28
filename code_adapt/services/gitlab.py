"""GitLab REST API client via httpx.

Compatible with gitlab.com, gitcode.com (which uses GitLab's API), and
self-hosted GitLab instances.
"""

from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

import httpx

from ..models import CommitSummary, PRSummary, ReleaseSummary


class GitLabClient:
    """Thin wrapper around the GitLab v4 REST API.

    Parameters
    ----------
    base_url:
        API base URL, e.g. ``https://gitlab.com/api/v4`` or
        ``https://gitcode.com/api/v4``.
    token:
        Personal-access or project-access token sent as ``PRIVATE-TOKEN``.
    """

    def __init__(self, base_url: str, token: str) -> None:
        # Strip trailing slash so callers don't have to worry about it.
        self.base_url = base_url.rstrip("/")
        self.token = token

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        """Authentication headers for GitLab API requests."""
        return {"PRIVATE-TOKEN": self.token}

    @staticmethod
    def _project_path(owner: str, repo: str) -> str:
        """URL-encode ``owner/repo`` for use in ``/projects/:id/`` endpoints."""
        return quote(f"{owner}/{repo}", safe="")

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url,
            headers=self._headers(),
            timeout=30.0,
        )

    # ------------------------------------------------------------------
    # Public API — return types mirror github.py
    # ------------------------------------------------------------------

    def fetch_commits(
        self, owner: str, repo: str, since: datetime | None = None
    ) -> list[CommitSummary]:
        """GET /projects/:id/repository/commits"""
        pid = self._project_path(owner, repo)
        with self._client() as client:
            params: dict = {"per_page": 100}
            if since:
                params["since"] = since.isoformat()
            resp = client.get(f"/projects/{pid}/repository/commits", params=params)
            resp.raise_for_status()
            return [
                CommitSummary(
                    sha=c["id"],
                    message=c["title"],
                    author=c.get("author_name", "unknown"),
                    date=c.get("committed_date", c.get("created_at", "")),
                )
                for c in resp.json()
            ]

    def fetch_merge_requests(
        self, owner: str, repo: str, since: datetime | None = None
    ) -> list[PRSummary]:
        """GET /projects/:id/merge_requests"""
        pid = self._project_path(owner, repo)
        with self._client() as client:
            params: dict = {
                "state": "all",
                "order_by": "updated_at",
                "sort": "desc",
                "per_page": 100,
            }
            if since:
                params["updated_after"] = since.isoformat()
            resp = client.get(f"/projects/{pid}/merge_requests", params=params)
            resp.raise_for_status()
            return [
                PRSummary(
                    number=mr["iid"],
                    title=mr["title"],
                    state=mr["state"],
                    author=mr.get("author", {}).get("username", "unknown"),
                    url=mr["web_url"],
                )
                for mr in resp.json()
            ]

    def fetch_releases(
        self, owner: str, repo: str, since: datetime | None = None
    ) -> list[ReleaseSummary]:
        """GET /projects/:id/releases"""
        pid = self._project_path(owner, repo)
        with self._client() as client:
            resp = client.get(f"/projects/{pid}/releases", params={"per_page": 100})
            resp.raise_for_status()
            releases = resp.json()
            if since:
                since_ts = since.timestamp()
                releases = [
                    r
                    for r in releases
                    if r.get("released_at")
                    and datetime.fromisoformat(
                        r["released_at"].replace("Z", "+00:00")
                    ).timestamp()
                    >= since_ts
                ]
            return [
                ReleaseSummary(
                    tag=r["tag_name"],
                    name=r.get("name") or r["tag_name"],
                    date=r.get("released_at") or r.get("created_at", ""),
                    url=r.get("_links", {}).get("self", ""),
                )
                for r in releases
            ]

    def fetch_mr_diff(
        self, owner: str, repo: str, mr_iid: int
    ) -> dict:
        """Return ``{files, additions, deletions, message}`` for a merge request.

        GET /projects/:id/merge_requests/:iid/changes
        """
        pid = self._project_path(owner, repo)
        with self._client() as client:
            resp = client.get(f"/projects/{pid}/merge_requests/{mr_iid}/changes")
            resp.raise_for_status()
            data = resp.json()
            changes = data.get("changes", [])
            files = [c.get("new_path", c.get("old_path", "")) for c in changes]
            # GitLab MR changes endpoint doesn't provide per-file line counts
            # directly; we count diff lines from the patch text.
            additions = 0
            deletions = 0
            for c in changes:
                diff_text = c.get("diff", "")
                for line in diff_text.splitlines():
                    if line.startswith("+") and not line.startswith("+++"):
                        additions += 1
                    elif line.startswith("-") and not line.startswith("---"):
                        deletions += 1
            return {
                "files": files,
                "additions": additions,
                "deletions": deletions,
                "message": data.get("title", ""),
            }

    def fetch_commit_diff(
        self, owner: str, repo: str, sha: str
    ) -> dict:
        """Return ``{files, additions, deletions, message}`` for a commit.

        GET /projects/:id/repository/commits/:sha and
        GET /projects/:id/repository/commits/:sha/diff
        """
        pid = self._project_path(owner, repo)
        with self._client() as client:
            # Fetch commit metadata for the message.
            commit_resp = client.get(f"/projects/{pid}/repository/commits/{sha}")
            commit_resp.raise_for_status()
            commit_data = commit_resp.json()

            # Fetch the diff.
            diff_resp = client.get(f"/projects/{pid}/repository/commits/{sha}/diff")
            diff_resp.raise_for_status()
            diffs = diff_resp.json()

            files = [d.get("new_path", d.get("old_path", "")) for d in diffs]
            additions = 0
            deletions = 0
            for d in diffs:
                diff_text = d.get("diff", "")
                for line in diff_text.splitlines():
                    if line.startswith("+") and not line.startswith("+++"):
                        additions += 1
                    elif line.startswith("-") and not line.startswith("---"):
                        deletions += 1
            return {
                "files": files,
                "additions": additions,
                "deletions": deletions,
                "message": commit_data.get("message", ""),
            }
