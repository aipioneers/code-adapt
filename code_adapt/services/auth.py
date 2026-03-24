"""GitHub authentication: gh CLI → GITHUB_TOKEN env → error."""

from __future__ import annotations

import os
import subprocess

from ..errors import AuthError


def get_github_token() -> str:
    # 1. Try `gh auth token`
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

    # 2. GITHUB_TOKEN env
    env_token = os.environ.get("GITHUB_TOKEN", "").strip()
    if env_token:
        return env_token

    raise AuthError(
        'No GitHub token found. Either run "gh auth login" or set the GITHUB_TOKEN environment variable.'
    )
