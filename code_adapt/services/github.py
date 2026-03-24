"""GitHub REST API client via httpx."""

from __future__ import annotations

import re
from datetime import datetime

import httpx

from ..errors import ValidationError
from ..models import CommitSummary, PRSummary, ReleaseSummary

API_BASE = "https://api.github.com"


def parse_repo_url(url: str) -> tuple[str, str]:
    """Extract (owner, repo) from a GitHub URL (HTTPS or SSH)."""
    m = re.search(r"github\.com[/:]([^/]+)/([^/.]+?)(?:\.git)?$", url)
    if not m:
        raise ValidationError(f"Cannot parse GitHub owner/repo from URL: {url}")
    return m.group(1), m.group(2)


def _client(token: str) -> httpx.Client:
    return httpx.Client(
        base_url=API_BASE,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=30.0,
    )


def _check_rate_limit(resp: httpx.Response) -> None:
    remaining = resp.headers.get("x-ratelimit-remaining")
    if remaining is not None and int(remaining) < 100:
        from rich import print as rprint

        rprint(f"[yellow]GitHub API rate limit low: {remaining} requests remaining.[/yellow]")


def fetch_commits(
    token: str, owner: str, repo: str, since: datetime | None = None
) -> list[CommitSummary]:
    with _client(token) as client:
        params: dict = {"per_page": 100}
        if since:
            params["since"] = since.isoformat()
        resp = client.get(f"/repos/{owner}/{repo}/commits", params=params)
        resp.raise_for_status()
        _check_rate_limit(resp)
        return [
            CommitSummary(
                sha=c["sha"],
                message=c["commit"]["message"].split("\n")[0],
                author=c["commit"]["author"]["name"]
                if c["commit"]["author"]
                else c.get("author", {}).get("login", "unknown"),
                date=c["commit"]["author"]["date"] if c["commit"]["author"] else "",
            )
            for c in resp.json()
        ]


def fetch_pull_requests(
    token: str, owner: str, repo: str, since: datetime | None = None
) -> list[PRSummary]:
    with _client(token) as client:
        resp = client.get(
            f"/repos/{owner}/{repo}/pulls",
            params={"state": "all", "sort": "updated", "direction": "desc", "per_page": 100},
        )
        resp.raise_for_status()
        _check_rate_limit(resp)
        prs = resp.json()
        if since:
            since_ts = since.timestamp()
            prs = [
                pr
                for pr in prs
                if datetime.fromisoformat(pr["updated_at"].replace("Z", "+00:00")).timestamp()
                >= since_ts
            ]
        return [
            PRSummary(
                number=pr["number"],
                title=pr["title"],
                state=pr["state"],
                author=pr.get("user", {}).get("login", "unknown"),
                url=pr["html_url"],
            )
            for pr in prs
        ]


def fetch_releases(
    token: str, owner: str, repo: str, since: datetime | None = None
) -> list[ReleaseSummary]:
    with _client(token) as client:
        resp = client.get(f"/repos/{owner}/{repo}/releases", params={"per_page": 100})
        resp.raise_for_status()
        _check_rate_limit(resp)
        releases = resp.json()
        if since:
            since_ts = since.timestamp()
            releases = [
                r
                for r in releases
                if r.get("published_at")
                and datetime.fromisoformat(
                    r["published_at"].replace("Z", "+00:00")
                ).timestamp()
                >= since_ts
            ]
        return [
            ReleaseSummary(
                tag=r["tag_name"],
                name=r.get("name") or r["tag_name"],
                date=r.get("published_at") or r["created_at"],
                url=r["html_url"],
            )
            for r in releases
        ]


def fetch_pr_diff(
    token: str, owner: str, repo: str, pr_number: int
) -> dict:
    """Return {files, additions, deletions, patch}."""
    with _client(token) as client:
        files_resp = client.get(
            f"/repos/{owner}/{repo}/pulls/{pr_number}/files", params={"per_page": 100}
        )
        files_resp.raise_for_status()
        _check_rate_limit(files_resp)
        file_data = files_resp.json()

        pr_resp = client.get(f"/repos/{owner}/{repo}/pulls/{pr_number}")
        pr_resp.raise_for_status()
        title = pr_resp.json()["title"]

        files = [f["filename"] for f in file_data]
        additions = sum(f["additions"] for f in file_data)
        deletions = sum(f["deletions"] for f in file_data)
        return {
            "files": files,
            "additions": additions,
            "deletions": deletions,
            "message": title,
        }


def fetch_commit_diff(
    token: str, owner: str, repo: str, sha: str
) -> dict:
    """Return {files, additions, deletions, message}."""
    with _client(token) as client:
        resp = client.get(f"/repos/{owner}/{repo}/commits/{sha}")
        resp.raise_for_status()
        _check_rate_limit(resp)
        data = resp.json()
        commit_files = data.get("files", [])
        return {
            "files": [f["filename"] for f in commit_files],
            "additions": sum(f["additions"] for f in commit_files),
            "deletions": sum(f["deletions"] for f in commit_files),
            "message": data["commit"]["message"],
        }


def fetch_release_info(token: str, owner: str, repo: str, tag: str) -> dict:
    """Return {name, message}."""
    with _client(token) as client:
        resp = client.get(f"/repos/{owner}/{repo}/releases/tags/{tag}")
        resp.raise_for_status()
        data = resp.json()
        return {"name": data.get("name") or tag, "message": data.get("name") or tag}
