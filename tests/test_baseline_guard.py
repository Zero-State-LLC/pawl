from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from pawl.baseline import Baseline, Quarantine, SuiteBaseline, check_quarantine, stricter
from pawl.config import load_config
from pawl.errors import ConfigError
from pawl.guard import baseline_changes, run_guard


def _suite(**kw: object) -> SuiteBaseline:
    base: dict[str, object] = {"failing_ids": [], "collected": 1, "collected_ids": ["a"]}
    base.update(kw)
    return SuiteBaseline(**base)  # type: ignore[arg-type]


def test_honest_tightening_is_protected_info_and_passes(demo_repo: Path) -> None:
    path = demo_repo / "pawl.baseline.json"
    data = json.loads(path.read_text())
    suite = next(iter(data["suites"].values()))
    suite["collected_ids"] = sorted([*suite["collected_ids"], "tests/test_new.py::test_x"])
    suite["collected"] = len(suite["collected_ids"])
    path.write_text(json.dumps(data, indent=2) + "\n")
    report = run_guard(load_config(demo_repo), "main")
    protected = [f for f in report.findings if f.rule == "PROTECTED_CHANGED"]
    assert [f.severity for f in protected] == ["info"]
    assert report.status == "pass"


def test_loosening_is_protected_block(demo_repo: Path) -> None:
    path = demo_repo / "pawl.baseline.json"
    data = json.loads(path.read_text())
    next(iter(data["suites"].values()))["confirmed_orders"] = 0
    path.write_text(json.dumps(data, indent=2) + "\n")
    report = run_guard(load_config(demo_repo), "main")
    assert {(f.rule, f.severity) for f in report.findings} >= {
        ("PROTECTED_CHANGED", "block"),
        ("BASELINE_LOOSENED", "block"),
    }


def test_quarantine_compared_whole() -> None:
    q = Quarantine("t", "x", "flaky", "2026-10-15")
    a = Baseline(suites={"t": _suite()}, quarantine=[q])
    longer = Baseline(
        suites={"t": _suite()}, quarantine=[Quarantine("t", "x", "flaky", "2099-01-01")]
    )
    shorter = Baseline(
        suites={"t": _suite()}, quarantine=[Quarantine("t", "x", "flaky", "2026-10-10")]
    )
    reason = Baseline(
        suites={"t": _suite()}, quarantine=[Quarantine("t", "x", "other", "2026-10-15")]
    )
    assert baseline_changes(a.dumps(), longer.dumps())[0] == [
        "quarantine changed: x until 2099-01-01 (flaky)"
    ]
    assert baseline_changes(a.dumps(), reason.dumps())[0]
    loosened, tightened = baseline_changes(a.dumps(), shorter.dumps())
    assert loosened == [] and tightened == ["quarantine shortened: x until 2026-10-10"]
    loosened, tightened = baseline_changes(a.dumps(), Baseline(suites={"t": _suite()}).dumps())
    assert loosened == [] and tightened == ["quarantine removed: x"]


def test_unrecognized_metric_fields_are_loosening() -> None:
    a = Baseline(metrics={"m": {"value": 1, "direction": "down"}})
    b = Baseline(metrics={"m": {"value": 1, "direction": "down", "slack": 5}})
    assert baseline_changes(a.dumps(), b.dumps())[0] == ["m: unrecognized metric fields changed"]


def test_added_suite_and_metric_are_tightening() -> None:
    a = Baseline(suites={"t": _suite()})
    b = Baseline(
        suites={"t": _suite(), "u": _suite()}, metrics={"m": {"value": 1, "direction": "down"}}
    )
    assert baseline_changes(a.dumps(), b.dumps()) == ([], ["u: suite added", "m: metric added"])


def test_stricter_keeps_the_earlier_expiry() -> None:
    a = Baseline(quarantine=[Quarantine("t", "x", "r", "2026-10-20")])
    b = Baseline(quarantine=[Quarantine("t", "x", "r", "2026-10-12")])
    assert stricter(a, b).quarantine[0].expires == "2026-10-12"
    assert stricter(b, a).quarantine[0].expires == "2026-10-12"


def test_check_quarantine_limit() -> None:
    today = dt.date(2026, 10, 8)
    ok = Baseline(quarantine=[Quarantine("t", "x", "r", "2026-11-07")])
    check_quarantine(ok, 30, today)
    long = Baseline(quarantine=[Quarantine("t", "x", "r", "2026-11-08")])
    with pytest.raises(ConfigError, match="quarantine_max_days"):
        check_quarantine(long, 30, today)


def test_check_quarantine_huge_max_days_does_not_overflow() -> None:
    today = dt.date(2026, 10, 8)
    check_quarantine(Baseline(), 999_999_999, today)
    q = Baseline(quarantine=[Quarantine("t", "x", "r", "2099-12-31")])
    check_quarantine(q, 999_999_999, today)


def test_guard_enforces_the_quarantine_limit_on_the_head_baseline(demo_repo: Path) -> None:
    """Shortening a quarantine is a tightening, but the result must still be within the limit."""
    path = demo_repo / "pawl.baseline.json"
    data = json.loads(path.read_text())
    suite = next(iter(data["suites"]))
    data["quarantine"] = [
        {"suite": suite, "id": "tests/test_x.py::t", "reason": "r", "expires": "2099-12-30"}
    ]
    path.write_text(json.dumps(data, indent=2) + "\n")
    report = run_guard(load_config(demo_repo), "main")
    blocks = [f for f in report.findings if f.severity == "block"]
    assert any(f.rule == "BASELINE_LOOSENED" and "quarantine_max_days" in f.message for f in blocks)
    assert ("PROTECTED_CHANGED", "block") in {(f.rule, f.severity) for f in blocks}
    assert report.status == "fail"
