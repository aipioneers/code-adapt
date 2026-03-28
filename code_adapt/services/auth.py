"""Authentication helpers: multi-provider token resolution.

Supports GitHub (``gh`` CLI + env var), GitLab, gitcode, and Gitea tokens.
"""

from __future__ import annotations

import os
import subprocess

from ..errors import AuthError

# Lazy import — only used when caller passes a Provider enum.
# Avoids a hard circular dependency; provider.py doesn't import auth.py.
from .provider import Provider

# Mapping of providers to their environment variable names.
_ENV_VAR_MAP: dict[Provider, str] = {
    Provider.GITHUB: "GITHUB_TOKEN",
    Provider.GITLAB: "GITLAB_TOKEN",
    Provider.GITCODE: "GITCODE_TOKEN",
    Provider.GITEA: "GITEA_TOKEN",
    Provider.GITEE: "GITEE_TOKEN",
}


def get_github_token() -> str:
    """Resolve a GitHub token.

    Resolution order:
    1. ``gh auth token`` (GitHub CLI)
    2. ``GITHUB_TOKEN`` environment variable

    Raises :class:`~code_adapt.errors.AuthError` when no token is found.

    This function is kept for backward compatibility.  New code should
    prefer :func:`get_token` with ``Provider.GITHUB``.
    """
    return get_token(Provider.GITHUB)


def get_token(provider: Provider) -> str:
    """Resolve an authentication token for the given provider.

    Resolution order per provider:

    * **GitHub** — ``gh auth token`` CLI, then ``GITHUB_TOKEN`` env var.
    * **GitLab** — ``GITLAB_TOKEN`` env var.
    * **gitcode** — ``GITCODE_TOKEN`` env var.
    * **Gitea**  — ``GITEA_TOKEN`` env var.
    * **Gitee**  — ``GITEE_TOKEN`` env var.

    Raises :class:`~code_adapt.errors.AuthError` when no token is found.
    """
    # GitHub has an extra CLI-based resolution step.
    if provider == Provider.GITHUB:
        token = _try_gh_cli()
        if token:
            return token

    # Try the environment variable.
    env_var = _ENV_VAR_MAP.get(provider)
    if env_var:
        env_token = os.environ.get(env_var, "").strip()
        if env_token:
            return env_token

    # Build a helpful error message.
    hints: dict[Provider, str] = {
        Provider.GITHUB: 'Run "gh auth login" or set the GITHUB_TOKEN environment variable.',
        Provider.GITLAB: "Set the GITLAB_TOKEN environment variable.",
        Provider.GITCODE: "Set the GITCODE_TOKEN environment variable.",
        Provider.GITEA: "Set the GITEA_TOKEN environment variable.",
        Provider.GITEE: "Set the GITEE_TOKEN environment variable.",
    }
    hint = hints.get(provider, f"Set a token for provider '{provider.value}'.")
    raise AuthError(f"No {provider.value} token found. {hint}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _try_gh_cli() -> str | None:
    """Attempt to retrieve a token from the ``gh`` CLI.  Returns *None* on failure."""
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        token = result.stdout.strip()
        if token:
            return token
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None
