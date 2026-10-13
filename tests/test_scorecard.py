"""Scorecard fields are additive and do not change the verdict."""

from __future__ import annotations

from pawl.check import Report, check_scorecard
from pawl.guard import Finding, GuardReport, guard_scorecard


def test_check_scorecard_counts_only_tests_above_the_floor() -> None:
    suites = [
        {"name": "core", "collected": 10, "baseline_collected": 8, "seconds": 1.5},
        {"name": "extra", "collected": 2, "baseline_collected": 4, "seconds": 0.25},
    ]
    card = check_scorecard(suites)
    assert card == {
        "unbaselined_tests": 2,
        "unbaselined_rate": 2 / 12,
        "suite_seconds": {"core": 1.5, "extra": 0.25},
    }
    report = Report(suites=suites)
    assert report.to_json()["scorecard"] == card
    assert report.to_json()["exit_code"] == 0


def test_check_scorecard_is_zero_when_nothing_was_collected() -> None:
    assert check_scorecard([]) == {
        "unbaselined_tests": 0,
        "unbaselined_rate": 0.0,
        "suite_seconds": {},
    }


def test_guard_scorecard_copies_approval_and_finding_rows() -> None:
    findings = [
        Finding("PROTECTED_CHANGED", "block", ".github/workflows/ci.yml", "edited"),
        Finding("SPEC_AUTHORITY_MOVED", "info", "specs/a.md", "moved"),
    ]
    approval = {"source": "label", "label": "pawl-approved", "sha": "abc123"}
    card = guard_scorecard(findings, approval)
    assert card == {
        "findings": [
            {
                "rule": "PROTECTED_CHANGED",
                "severity": "block",
                "path": ".github/workflows/ci.yml",
            },
            {"rule": "SPEC_AUTHORITY_MOVED", "severity": "info", "path": "specs/a.md"},
        ],
        "approval_source": "label",
        "approval_sha": "abc123",
    }
    report = GuardReport(base="main", findings=findings, approval=approval)
    assert report.to_json()["scorecard"] == card
    assert report.status == "fail"


def test_guard_scorecard_without_approval_is_null() -> None:
    card = guard_scorecard([], None)
    assert card["approval_source"] is None
    assert card["approval_sha"] is None
    assert card["findings"] == []
    report = GuardReport(base="main")
    assert report.to_json()["scorecard"] == card
    assert report.to_json()["exit_code"] == 0
