from __future__ import annotations

import datetime as dt
from pathlib import Path

from pawl.adapters import SuiteRun
from pawl.baseline import Baseline, Quarantine, SuiteBaseline
from pawl.check import Measurement, compare, compare_suite
from pawl.config import MetricConfig, SuiteConfig, parse_config

SUITE = SuiteConfig(name="t", adapter="pytest", command=("x",), isolate_max=0)
IDS = ["a", "b", "c", "d"]


def base(
    failing: list[str], skipped: list[str] | None = None, identity: str = "ids"
) -> SuiteBaseline:
    return SuiteBaseline(
        failing_ids=failing,
        collected=len(IDS),
        collected_ids=IDS if identity == "ids" else [],
        skipped_ids=skipped or [],
        identity=identity,
    )


def run(outcomes: dict[str, str], order: str = "default") -> SuiteRun:
    return SuiteRun(outcomes=outcomes, order=order)


def codes(problems: list) -> list[str]:  # type: ignore[type-arg]
    return sorted(p.code for p in problems)


def test_identical_state_passes() -> None:
    problems, notes, _ = compare_suite(
        SUITE,
        base(["a"]),
        [run({"a": "failed", "b": "passed", "c": "passed", "d": "passed"})],
        set(),
        True,
    )
    assert problems == [] and notes == []


def test_swapped_failure_same_count_is_caught() -> None:
    cur = {"a": "passed", "b": "failed", "c": "passed", "d": "passed"}
    problems, _, _ = compare_suite(SUITE, base(["a"]), [run(cur)], set(), lock=False)
    assert codes(problems) == ["NEW_FAILURE"]
    assert problems[0].ids == ["b"]


def test_swapped_failure_passes_in_count_mode() -> None:
    cur = {"a": "passed", "b": "failed", "c": "passed", "d": "passed"}
    problems, notes, _ = compare_suite(
        SUITE, base(["a"], identity="count"), [run(cur)], set(), lock=False
    )
    assert problems == []
    assert any("now pass" in n for n in notes)


def test_deleted_test_replaced_by_new_one_is_caught() -> None:
    cur = {"a": "failed", "b": "passed", "c": "passed", "e": "passed"}
    problems, _, _ = compare_suite(SUITE, base(["a"]), [run(cur)], set(), lock=False)
    assert codes(problems) == ["MISSING_TESTS"]
    assert problems[0].ids == ["d"]


def test_collection_drop_and_new_skip() -> None:
    cur = {"a": "failed", "b": "skipped", "c": "passed"}
    problems, _, _ = compare_suite(SUITE, base(["a"]), [run(cur)], set(), lock=False)
    assert codes(problems) == ["COLLECTION_DROP", "MISSING_TESTS", "NEWLY_SKIPPED"]


def test_fixed_failure_is_stale_only_under_lock() -> None:
    cur = {"a": "passed", "b": "passed", "c": "passed", "d": "passed"}
    problems, _, _ = compare_suite(SUITE, base(["a"]), [run(cur)], set(), lock=True)
    assert codes(problems) == ["STALE_BASELINE"]
    problems, notes, _ = compare_suite(SUITE, base(["a"]), [run(cur)], set(), lock=False)
    assert problems == [] and notes


def test_missing_known_failure_is_not_reported_fixed() -> None:
    cur = {"b": "passed", "c": "passed", "d": "passed"}
    problems, notes, _ = compare_suite(SUITE, base(["a"]), [run(cur)], set(), lock=True)
    assert codes(problems) == ["COLLECTION_DROP", "MISSING_TESTS"]
    assert not any("now pass" in n for n in notes)


def test_order_dependent_failure() -> None:
    ok = {k: "passed" for k in IDS}
    alt = dict(ok, c="failed")
    problems, _, _ = compare_suite(
        SUITE, base([]), [run(ok), run(alt, "reverse")], set(), lock=False
    )
    assert codes(problems) == ["ORDER_DEPENDENT_FAILURE"]


def test_quarantine_excuses_and_expires() -> None:
    cur = {"a": "passed", "b": "failed", "c": "passed", "d": "passed"}
    problems, _, _ = compare_suite(SUITE, base([]), [run(cur)], {"b"}, lock=True)
    assert problems == []


def test_compare_metrics_and_structure(tmp_path: Path) -> None:
    cfg = parse_config(
        """
[[suite]]
name = "t"
adapter = "pytest"
command = "x"
isolate_max = 0
[[metric]]
name = "lint"
command = "x"
direction = "down"
extract = "count-lines"
[[metric]]
name = "cov"
command = "x"
direction = "up"
extract = "count-lines"
""",
        tmp_path,
    )
    bl = Baseline(
        suites={"t": base([]), "old": base([])},
        metrics={
            "lint": {"value": 3, "direction": "down"},
            "cov": {"value": 80, "direction": "up"},
        },
        quarantine=[Quarantine("t", "zz", "r", "2000-01-01")],
    )
    m = Measurement(suites={"t": [run({k: "passed" for k in IDS})]}, metrics={"lint": 4, "cov": 90})
    report = compare(cfg, bl, m, lock=True, today=dt.date(2026, 1, 1))
    assert codes(report.problems) == ["METRIC_REGRESSION", "STALE_BASELINE", "SUITE_REMOVED"]
    assert report.status == "fail"
    data = report.to_json()
    assert data["next_steps"]
    assert any("expired" in n for n in report.notes)


def test_missing_baseline_entry_fails(tmp_path: Path) -> None:
    cfg = parse_config('[[suite]]\nname="t"\nadapter="pytest"\ncommand="x"', tmp_path)
    m = Measurement(suites={"t": [run({"a": "passed"})]})
    report = compare(cfg, Baseline(), m, lock=False)
    assert codes(report.problems) == ["NOT_IN_BASELINE"]


def test_metric_config_type() -> None:
    assert MetricConfig("m", ("x",), "down", "count-lines").direction == "down"


def test_new_collected_id_fails_until_update() -> None:
    cur = {"a": "failed", "b": "passed", "c": "passed", "d": "passed", "e": "passed"}
    problems, notes, _ = compare_suite(SUITE, base(["a"]), [run(cur)], set(), lock=False)
    assert codes(problems) == ["UNBASELINED_TESTS"]
    assert problems[0].ids == ["e"]
    assert notes == []
    assert "pawl update" in problems[0].message


def test_count_mode_collection_growth_fails() -> None:
    cur = {"a": "failed", "b": "passed", "c": "passed", "d": "passed", "e": "passed"}
    problems, notes, _ = compare_suite(
        SUITE, base(["a"], identity="count"), [run(cur)], set(), lock=False
    )
    assert codes(problems) == ["UNBASELINED_TESTS"]
    assert problems[0].ids == []
    assert "1 new test" in problems[0].message
    assert notes == []


def test_growth_with_a_missing_id_names_both() -> None:
    cur = {"a": "failed", "b": "passed", "c": "passed", "e": "passed", "f": "passed"}
    problems, _, _ = compare_suite(SUITE, base(["a"]), [run(cur)], set(), lock=False)
    assert codes(problems) == ["MISSING_TESTS", "UNBASELINED_TESTS"]
    by_code = {p.code: p.ids for p in problems}
    assert by_code["MISSING_TESTS"] == ["d"]
    assert by_code["UNBASELINED_TESTS"] == ["e", "f"]
