"""Relevance and risk assessment logic."""

from __future__ import annotations

from dataclasses import dataclass

from ..models import (
    Analysis,
    Policy,
    Profile,
    RelevanceScore,
    RiskScore,
    SuggestedAction,
)


@dataclass
class AssessmentResult:
    relevance: RelevanceScore
    risk_score: RiskScore
    strategic_value: str
    suggested_action: SuggestedAction


def assess_relevance(analysis: Analysis, profile: Profile, policy: Policy) -> AssessmentResult:
    relevance = _compute_relevance(analysis, profile, policy)
    risk = _compute_risk(analysis)
    action = _compute_suggested_action(relevance, risk)
    value = _compute_strategic_value(analysis, profile)
    return AssessmentResult(
        relevance=relevance, risk_score=risk, strategic_value=value, suggested_action=action
    )


def _compute_relevance(
    analysis: Analysis, profile: Profile, policy: Policy
) -> RelevanceScore:
    modules = analysis.affected_modules
    if profile.critical_modules and any(m in profile.critical_modules for m in modules):
        return RelevanceScore.HIGH
    if policy.ignored_modules and all(m in policy.ignored_modules for m in modules):
        return RelevanceScore.LOW
    if policy.relevant_modules and any(m in policy.relevant_modules for m in modules):
        return RelevanceScore.MEDIUM
    return RelevanceScore.MEDIUM


def _compute_risk(analysis: Analysis) -> RiskScore:
    if analysis.classification.value == "security":
        return RiskScore.HIGH
    if analysis.diff_stats.files_changed > 20 or analysis.diff_stats.additions > 500:
        return RiskScore.HIGH
    if analysis.diff_stats.files_changed > 5:
        return RiskScore.MEDIUM
    return RiskScore.LOW


def _compute_suggested_action(
    relevance: RelevanceScore, risk: RiskScore
) -> SuggestedAction:
    if relevance == RelevanceScore.HIGH and risk == RiskScore.LOW:
        return SuggestedAction.ADOPT
    if relevance == RelevanceScore.HIGH and risk == RiskScore.HIGH:
        return SuggestedAction.ADAPT_PARTIALLY
    if relevance == RelevanceScore.HIGH:
        return SuggestedAction.ADOPT
    if relevance == RelevanceScore.MEDIUM:
        return SuggestedAction.MONITOR
    return SuggestedAction.IGNORE


def _compute_strategic_value(analysis: Analysis, profile: Profile) -> str:
    if not profile.priorities:
        modules_str = ", ".join(analysis.affected_modules) or "unknown modules"
        return f"Relevant {analysis.classification.value} change in {modules_str}."

    intent_lower = analysis.intent.lower()
    matching = [p for p in profile.priorities if p.lower() in intent_lower]
    if matching:
        return f"Aligns with priorities: {', '.join(matching)}."

    label = analysis.classification.value.capitalize()
    return f"{label} change; review for alignment with project goals."
