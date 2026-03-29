"""Pydantic models for code-adapt entities."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .errors import ValidationError


# --- Enums -------------------------------------------------------------------


class AdaptationStatus(str, Enum):
    OBSERVED = "observed"
    ANALYZED = "analyzed"
    ASSESSED = "assessed"
    PLANNED = "planned"
    IMPLEMENTED = "implemented"
    VALIDATED = "validated"
    CONTRIBUTED = "contributed"
    MERGED = "merged"
    REJECTED = "rejected"


class RelevanceScore(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RiskScore(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SuggestedAction(str, Enum):
    ADOPT = "adopt"
    IGNORE = "ignore"
    MONITOR = "monitor"
    ADAPT_PARTIALLY = "adapt-partially"


class Strategy(str, Enum):
    DIRECT_ADOPTION = "direct-adoption"
    PARTIAL_REIMPLEMENTATION = "partial-reimplementation"
    IMPROVED_IMPLEMENTATION = "improved-implementation"


class Classification(str, Enum):
    FEATURE = "feature"
    BUGFIX = "bugfix"
    REFACTOR = "refactor"
    SECURITY = "security"
    UNKNOWN = "unknown"


# --- Valid state transitions --------------------------------------------------

VALID_TRANSITIONS: dict[AdaptationStatus, list[AdaptationStatus]] = {
    AdaptationStatus.OBSERVED: [
        AdaptationStatus.ANALYZED,
        AdaptationStatus.PLANNED,
        AdaptationStatus.REJECTED,
    ],
    AdaptationStatus.ANALYZED: [
        AdaptationStatus.ASSESSED,
        AdaptationStatus.PLANNED,
        AdaptationStatus.REJECTED,
    ],
    AdaptationStatus.ASSESSED: [AdaptationStatus.PLANNED, AdaptationStatus.REJECTED],
    AdaptationStatus.PLANNED: [AdaptationStatus.IMPLEMENTED, AdaptationStatus.REJECTED],
    AdaptationStatus.IMPLEMENTED: [AdaptationStatus.VALIDATED, AdaptationStatus.REJECTED],
    AdaptationStatus.VALIDATED: [
        AdaptationStatus.CONTRIBUTED,
        AdaptationStatus.MERGED,
        AdaptationStatus.REJECTED,
    ],
    AdaptationStatus.CONTRIBUTED: [AdaptationStatus.MERGED, AdaptationStatus.REJECTED],
    AdaptationStatus.MERGED: [],
    AdaptationStatus.REJECTED: [],
}


def can_transition(from_status: AdaptationStatus, to_status: AdaptationStatus) -> bool:
    return to_status in VALID_TRANSITIONS[from_status]


# --- Repository ---------------------------------------------------------------


class Repository(BaseModel):
    name: str
    url: str
    type: Literal["upstream", "downstream"]
    default_branch: str = "main"
    provider: str = "github"
    license: str | None = None
    tech_stack: list[str] = Field(default_factory=list)
    xinchuang_compatible: bool | None = Field(
        default=None,
        description="China IT innovation (Xinchuang) compliance flag. Set by compliance checks.",
    )
    added_at: str = Field(default_factory=lambda: _now_iso())

    @model_validator(mode="after")
    def validate_fields(self) -> "Repository":
        if not self.name.strip():
            raise ValidationError("Repository name is required.")
        if not self.url.strip():
            raise ValidationError("Repository URL is required.")
        self.name = self.name.strip()
        self.url = self.url.strip()
        return self


# --- Observation --------------------------------------------------------------


class CommitSummary(BaseModel):
    sha: str
    message: str
    author: str
    date: str


class PRSummary(BaseModel):
    number: int
    title: str
    state: str
    author: str
    url: str


class ReleaseSummary(BaseModel):
    tag: str
    name: str
    date: str
    url: str


class SecurityAlert(BaseModel):
    id: str
    severity: str
    summary: str


class Observation(BaseModel):
    id: str
    repo_name: str
    timestamp: str = Field(default_factory=lambda: _now_iso())
    since: str | None = None
    commits: list[CommitSummary] = Field(default_factory=list)
    pull_requests: list[PRSummary] = Field(default_factory=list)
    releases: list[ReleaseSummary] = Field(default_factory=list)
    security_alerts: list[SecurityAlert] = Field(default_factory=list)


# --- Analysis -----------------------------------------------------------------


class DiffStats(BaseModel):
    additions: int
    deletions: int
    files_changed: int


class Analysis(BaseModel):
    id: str
    observation_id: str | None = None
    source_ref: str
    source_ref_type: Literal["pr", "commit", "release"]
    repo_name: str
    summary: str
    classification: Classification
    intent: str
    affected_files: list[str] = Field(default_factory=list)
    affected_modules: list[str] = Field(default_factory=list)
    diff_stats: DiffStats
    created_at: str = Field(default_factory=lambda: _now_iso())


# --- Adaptation ---------------------------------------------------------------


class Adaptation(BaseModel):
    id: str
    source_repo: str
    source_ref: str
    source_ref_type: Literal["pr", "commit", "release"]
    analysis_id: str | None = None
    status: AdaptationStatus
    relevance: RelevanceScore | None = None
    risk_score: RiskScore | None = None
    suggested_action: SuggestedAction | None = None
    strategy: Strategy | None = None
    target_modules: list[str] = Field(default_factory=list)
    plan_id: str | None = None
    branch: str | None = None
    created_at: str = Field(default_factory=lambda: _now_iso())
    updated_at: str = Field(default_factory=lambda: _now_iso())

    def transition(self, to: AdaptationStatus) -> "Adaptation":
        if not can_transition(self.status, to):
            allowed = VALID_TRANSITIONS[self.status]
            allowed_str = ", ".join(s.value for s in allowed) if allowed else "none"
            raise ValidationError(
                f'Invalid status transition: "{self.status.value}" → "{to.value}". '
                f"Allowed transitions: {allowed_str}."
            )
        return self.model_copy(update={"status": to, "updated_at": _now_iso()})


# --- Plan ---------------------------------------------------------------------


class PlanStep(BaseModel):
    order: int
    description: str
    target_file: str
    type: Literal["create", "modify", "delete", "test"]


class ContributionSplit(BaseModel):
    upstream: list[str] = Field(default_factory=list)
    internal: list[str] = Field(default_factory=list)


class Plan(BaseModel):
    id: str
    adaptation_id: str
    strategy: str
    target_modules: list[str] = Field(default_factory=list)
    steps: list[PlanStep] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    suggested_tests: list[str] = Field(default_factory=list)
    contribution_split: ContributionSplit | None = None
    created_at: str = Field(default_factory=lambda: _now_iso())


# --- Policy -------------------------------------------------------------------


class ContributionRules(BaseModel):
    enabled: bool = False
    require_review: bool = True
    exclude_patterns: list[str] = Field(default_factory=list)


class Policy(BaseModel):
    relevant_modules: list[str] = Field(default_factory=list)
    ignored_modules: list[str] = Field(default_factory=list)
    critical_licenses: list[str] = Field(default_factory=lambda: ["GPL-3.0", "AGPL-3.0"])
    protected_paths: list[str] = Field(default_factory=list)
    contribution_rules: ContributionRules = Field(default_factory=ContributionRules)
    auto_assess_threshold: str | None = None


# --- Profile ------------------------------------------------------------------


class Profile(BaseModel):
    name: str
    stack: list[str] = Field(default_factory=list)
    architecture: str = ""
    conventions: list[str] = Field(default_factory=list)
    critical_modules: list[str] = Field(default_factory=list)
    priorities: list[str] = Field(default_factory=list)


# --- Learning -----------------------------------------------------------------


class LearningRecord(BaseModel):
    adaptation_id: str
    outcome: Literal["accepted", "rejected"]
    reason: str | None = None
    recorded_at: str = Field(default_factory=lambda: _now_iso())


# --- Helpers ------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
