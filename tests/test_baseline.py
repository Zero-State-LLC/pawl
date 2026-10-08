from __future__ import annotations

import datetime as dt

import pytest

from pawl.baseline import Baseline, Quarantine, SuiteBaseline, parse_baseline, stricter
from pawl.errors import ConfigError


def make(failing: list[str], ids: list[str], skipped: list[str] | None = None) -> Baseline:
    return Baseline(
        suites={
            "t": SuiteBaseline(
                failing_ids=failing,
                collected=len(ids),
                collected_ids=ids,
                skipped_ids=skipped or [],
            )
        },
        metrics={
            "lint": {"value": 5, "direction": "down"},
            "cov": {"value": 80, "direction": "up"},
        },
    )


def test_roundtrip() -> None:
    b = make(["a"], ["a", "b"])
    b.quarantine.append(Quarantine("t", "b", "flaky network", "2030-01-01"))
    again = parse_baseline(b.dumps())
    assert again.suites["t"].failing_ids == ["a"]
    assert again.suites["t"].collected_ids == ["a", "b"]
    assert again.quarantine[0].reason == "flaky network"
    assert again.active_quarantine("t", dt.date(2029, 1, 1)) == {"b"}
    assert again.active_quarantine("t", dt.date(2031, 1, 1)) == set()


@pytest.mark.parametrize(
    "text",
    [
        "{}",
        "not json",
        '{"pawl_baseline": 1, "suites": {"t": {"failures": 2, "failing_ids": ["a"]}}}',
        '{"pawl_baseline": 1, "suites": {"t": {"collected": 3, "collected_ids": ["a"]}}}',
        '{"pawl_baseline": 1, "metrics": {"m": {"value": "x", "direction": "down"}}}',
        '{"pawl_baseline": 1, "quarantine": [{"suite": "t"}]}',
    ],
)
def test_inconsistent_baselines_are_rejected(text: str) -> None:
    with pytest.raises(ConfigError):
        parse_baseline(text)


def test_stricter_keeps_the_strictest_of_each_field() -> None:
    base = make(["a", "b"], ["a", "b", "c"])
    head = make(["a", "z"], ["a", "b"])  # head drops test c and adds failure z
    head.metrics = {
        "lint": {"value": 9, "direction": "down"},
        "cov": {"value": 70, "direction": "up"},
    }
    s = stricter(base, head)
    suite = s.suites["t"]
    assert suite.failing_ids == ["a"]
    assert suite.collected_ids == ["a", "b", "c"]
    assert suite.collected == 3
    assert s.metrics["lint"]["value"] == 5
    assert s.metrics["cov"]["value"] == 80
