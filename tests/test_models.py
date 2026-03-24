"""Tests for Pydantic models and state machine."""

import pytest

from code_adapt.errors import ValidationError
from code_adapt.models import (
    Adaptation,
    AdaptationStatus,
    Policy,
    Profile,
    RelevanceScore,
    Repository,
    can_transition,
)


class TestRepository:
    def test_create_valid(self):
        repo = Repository(name="myrepo", url="https://github.com/a/b", type="upstream")
        assert repo.name == "myrepo"
        assert repo.default_branch == "main"
        assert repo.tech_stack == []

    def test_strips_whitespace(self):
        repo = Repository(name="  myrepo  ", url=" https://github.com/a/b ", type="upstream")
        assert repo.name == "myrepo"
        assert repo.url == "https://github.com/a/b"

    def test_empty_name_raises(self):
        with pytest.raises(ValidationError):
            Repository(name="", url="https://github.com/a/b", type="upstream")

    def test_empty_url_raises(self):
        with pytest.raises(ValidationError):
            Repository(name="test", url="", type="upstream")


class TestAdaptationStateMachine:
    def test_valid_transitions(self):
        assert can_transition(AdaptationStatus.OBSERVED, AdaptationStatus.ANALYZED)
        assert can_transition(AdaptationStatus.ASSESSED, AdaptationStatus.PLANNED)
        assert can_transition(AdaptationStatus.VALIDATED, AdaptationStatus.CONTRIBUTED)

    def test_invalid_transitions(self):
        assert not can_transition(AdaptationStatus.MERGED, AdaptationStatus.OBSERVED)
        assert not can_transition(AdaptationStatus.REJECTED, AdaptationStatus.PLANNED)
        assert not can_transition(AdaptationStatus.OBSERVED, AdaptationStatus.IMPLEMENTED)

    def test_rejection_from_any_active_state(self):
        for status in (
            AdaptationStatus.OBSERVED,
            AdaptationStatus.ANALYZED,
            AdaptationStatus.ASSESSED,
            AdaptationStatus.PLANNED,
            AdaptationStatus.IMPLEMENTED,
            AdaptationStatus.VALIDATED,
            AdaptationStatus.CONTRIBUTED,
        ):
            assert can_transition(status, AdaptationStatus.REJECTED)

    def test_transition_updates_status(self):
        adp = Adaptation(
            id="adp_2026_001",
            source_repo="upstream",
            source_ref="pr-1",
            source_ref_type="pr",
            status=AdaptationStatus.OBSERVED,
        )
        updated = adp.transition(AdaptationStatus.ANALYZED)
        assert updated.status == AdaptationStatus.ANALYZED
        assert updated.updated_at != adp.updated_at

    def test_invalid_transition_raises(self):
        adp = Adaptation(
            id="adp_2026_001",
            source_repo="upstream",
            source_ref="pr-1",
            source_ref_type="pr",
            status=AdaptationStatus.MERGED,
        )
        with pytest.raises(ValidationError):
            adp.transition(AdaptationStatus.OBSERVED)


class TestPolicy:
    def test_defaults(self):
        p = Policy()
        assert p.critical_licenses == ["GPL-3.0", "AGPL-3.0"]
        assert p.contribution_rules.enabled is False
        assert p.contribution_rules.require_review is True


class TestProfile:
    def test_defaults(self):
        p = Profile(name="test")
        assert p.stack == []
        assert p.architecture == ""
