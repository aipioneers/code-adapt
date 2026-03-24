"""Shared pytest fixtures for code-adapt tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a temporary project with initialized .adapt/ directory."""
    adapt_dir = tmp_path / ".adapt"
    for sub in ("cache", "context", "analyses", "adaptations", "reports", "logs", "state"):
        (adapt_dir / sub).mkdir(parents=True)

    import json
    import yaml

    (adapt_dir / "config.yaml").write_text(yaml.dump({"version": "1.0"}))
    (adapt_dir / "repos.yaml").write_text(yaml.dump([]))
    (adapt_dir / "policies.yaml").write_text(yaml.dump({
        "relevant_modules": [],
        "ignored_modules": [],
        "critical_licenses": ["GPL-3.0", "AGPL-3.0"],
        "protected_paths": [],
        "contribution_rules": {"enabled": False, "require_review": True, "exclude_patterns": []},
        "auto_assess_threshold": None,
    }))
    (adapt_dir / "profile.yaml").write_text(yaml.dump({
        "name": "test-project",
        "stack": [],
        "architecture": "",
        "conventions": [],
        "critical_modules": [],
        "priorities": [],
    }))
    (adapt_dir / "state" / "counter.json").write_text(json.dumps({"obs": 0, "ana": 0, "adp": 0, "plan": 0}))

    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(old_cwd)
