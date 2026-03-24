"""Change classification via regex rules."""

from __future__ import annotations

import re

from ..models import Classification, DiffStats


def classify_change(
    message: str, files: list[str], additions: int, deletions: int
) -> Classification:
    """Classify a change. Rules checked in order, first match wins:
    1. Security — CVE/security/vulnerability/exploit
    2. Bugfix — fix/bug/patch/hotfix/resolve
    3. Refactor — refactor/cleanup/rename/reorganize/restructure
    4. Feature — feat/add/new/implement/introduce OR many new lines
    5. Default — unknown
    """
    if re.search(r"\b(cve|security|vulnerab|exploit)\b", message, re.I) or any(
        re.match(r"^(security|auth|cve)", f, re.I) for f in files
    ):
        return Classification.SECURITY

    if re.search(r"\b(fix|bug|patch|hotfix|resolve)\b", message, re.I):
        return Classification.BUGFIX

    if re.search(r"\b(refactor|cleanup|rename|reorganize|restructure)\b", message, re.I):
        return Classification.REFACTOR

    if re.search(r"\b(feat|add|new|implement|introduce)\b", message, re.I) or (
        additions > deletions * 3 and additions > 50
    ):
        return Classification.FEATURE

    return Classification.UNKNOWN


def extract_modules(files: list[str]) -> list[str]:
    """Extract logical module names from file paths.
    Groups by top-level directory (src/X/... → module "X").
    """
    modules: set[str] = set()
    for file in files:
        parts = file.split("/")
        if len(parts) <= 1:
            modules.add("root")
        elif parts[0] == "src" and len(parts) > 2:
            modules.add(parts[1])
        else:
            modules.add(parts[0])
    return sorted(modules)


def generate_summary(message: str, classification: Classification, stats: DiffStats) -> str:
    label = classification.value.capitalize()
    s = "s" if stats.files_changed != 1 else ""
    return f"{label}: {message} (+{stats.additions}/-{stats.deletions} in {stats.files_changed} file{s})"


def extract_intent(message: str) -> str:
    """Extract first sentence from a message."""
    first_line = message.split("\n")[0].strip()
    m = re.match(r"^(.+?[.!])\s", first_line)
    return m.group(1) if m else first_line
