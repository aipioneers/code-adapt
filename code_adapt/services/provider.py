"""Multi-provider abstraction for git hosting platforms.

Supports GitHub, GitLab, Gitea, gitcode.com, and custom/self-hosted instances.
"""

from __future__ import annotations

import re
from enum import Enum
from urllib.parse import urlparse

from ..errors import ValidationError


class Provider(str, Enum):
    GITHUB = "github"
    GITLAB = "gitlab"
    GITEA = "gitea"
    GITCODE = "gitcode"
    UNKNOWN = "unknown"


# Mapping of well-known hostnames to providers.
_DOMAIN_MAP: dict[str, Provider] = {
    "github.com": Provider.GITHUB,
    "gitlab.com": Provider.GITLAB,
    "gitcode.com": Provider.GITCODE,
    "gitcode.net": Provider.GITCODE,
    # Gitea's flagship public instance
    "gitea.com": Provider.GITEA,
    "codeberg.org": Provider.GITEA,
}

# Default API base URLs for cloud-hosted providers.
_API_BASE_MAP: dict[Provider, str] = {
    Provider.GITHUB: "https://api.github.com",
    Provider.GITLAB: "https://gitlab.com/api/v4",
    Provider.GITCODE: "https://gitcode.com/api/v4",
    Provider.GITEA: "https://gitea.com/api/v1",
}


def detect_provider(url: str) -> Provider:
    """Detect the git hosting provider from a URL (HTTPS or SSH).

    Inspects the hostname against a list of well-known domains.  Returns
    ``Provider.UNKNOWN`` when no match is found (e.g. a self-hosted instance
    whose domain hasn't been registered).

    Examples::

        detect_provider("https://github.com/owner/repo")          # GITHUB
        detect_provider("git@gitlab.com:owner/repo.git")           # GITLAB
        detect_provider("https://my-gitea.example.com/owner/repo") # UNKNOWN
    """
    host = _extract_host(url)
    return _DOMAIN_MAP.get(host, Provider.UNKNOWN)


def parse_repo_url(url: str) -> tuple[str, str]:
    """Extract ``(owner, repo)`` from any git hosting URL.

    Supports both HTTPS and SSH formats for all providers::

        https://github.com/owner/repo
        https://github.com/owner/repo.git
        git@github.com:owner/repo.git
        ssh://git@gitlab.com/owner/repo.git

    Raises :class:`~code_adapt.errors.ValidationError` when the URL cannot be
    parsed into an owner/repo pair.
    """
    # Normalise SSH shorthand (git@host:owner/repo) into a pseudo-URL so that
    # urlparse can handle every format uniformly.
    normalised = _normalise_ssh(url)
    parsed = urlparse(normalised)

    # For HTTPS/SSH URLs the path is e.g. "/owner/repo.git".
    # Strip leading/trailing slashes and the .git suffix, then split.
    path = parsed.path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]

    parts = path.split("/") if path else []
    if len(parts) < 2:
        raise ValidationError(f"Cannot parse owner/repo from URL: {url}")

    # Take the first two meaningful segments (owner/repo).
    return parts[0], parts[1]


def api_base_url(provider: Provider, url: str | None = None) -> str:
    """Return the REST API base URL for the given provider.

    For well-known cloud providers the canonical API URL is returned.  When
    *url* is given and the provider is ``UNKNOWN`` (or a self-hosted instance),
    the base URL is derived from the repository URL.

    For self-hosted GitLab / Gitea the caller should supply the original
    repository *url* so that the correct scheme and hostname are used.

    Raises :class:`~code_adapt.errors.ValidationError` when the API base
    cannot be determined.
    """
    host = _extract_host(url) if url else None

    # If we have a URL, check whether the host is a known cloud domain.
    # If so, return the canonical cloud API URL.  If NOT, this is a
    # self-hosted instance and we must derive the API base from the URL
    # rather than falling back to the cloud default.
    if host and host in _DOMAIN_MAP:
        known_provider = _DOMAIN_MAP[host]
        if known_provider in _API_BASE_MAP:
            return _API_BASE_MAP[known_provider]

    if host and host not in _DOMAIN_MAP and url:
        # Self-hosted: derive from the repository URL.
        scheme, netloc = _extract_scheme_netloc(url)
        if provider == Provider.GITLAB:
            return f"{scheme}://{netloc}/api/v4"
        if provider == Provider.GITEA:
            return f"{scheme}://{netloc}/api/v1"
        # Generic fallback — just return the base.
        return f"{scheme}://{netloc}"

    # No URL provided — use the cloud default for the provider enum.
    if provider in _API_BASE_MAP:
        return _API_BASE_MAP[provider]

    raise ValidationError(
        f"Cannot determine API base URL for provider '{provider.value}' without a repository URL."
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_host(url: str) -> str:
    """Return the lowercase hostname from an HTTPS or SSH URL."""
    # Handle SSH shorthand: git@host:owner/repo
    ssh_m = re.match(r"^[\w.-]+@([\w.-]+):", url)
    if ssh_m:
        return ssh_m.group(1).lower()

    parsed = urlparse(url)
    if parsed.hostname:
        return parsed.hostname.lower()

    raise ValidationError(f"Cannot extract hostname from URL: {url}")


def _normalise_ssh(url: str) -> str:
    """Turn ``git@host:owner/repo`` into ``ssh://git@host/owner/repo``."""
    m = re.match(r"^([\w.-]+@[\w.-]+):(.+)$", url)
    if m:
        return f"ssh://{m.group(1)}/{m.group(2)}"
    return url


def _extract_scheme_netloc(url: str) -> tuple[str, str]:
    """Return ``(scheme, netloc)`` — normalises SSH URLs first."""
    normalised = _normalise_ssh(url)
    parsed = urlparse(normalised)
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc or parsed.hostname or ""
    # Strip user info for API base (e.g. git@host → host)
    if "@" in netloc:
        netloc = netloc.split("@", 1)[1]
    return scheme, netloc
