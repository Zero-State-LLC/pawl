"""Measure the current state and compare it with the baseline."""

from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pawl import __version__
from pawl.adapters import SuiteRun, isolate, run_suite
from pawl.baseline import Baseline, SuiteBaseline
from pawl.config import Config, MetricConfig, SuiteConfig
from pawl.contract import SCHEMA_VERSION, exit_code_for
from pawl.metrics import measure, metric_delta

MAX_LISTED = 25


def in_ci() -> bool:
    return os.environ.get("CI", "").lower() in ("1", "true", "yes")


@dataclass
class Problem:
    """One reason the gate is red."""

    code: str
    subject: str
    message: str
    ids: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "subject": self.subject,
            "message": self.message,
            "ids": self.ids[:MAX_LISTED],
            "ids_total": len(self.ids),
        }


@dataclass
class Measurement:
    """Raw results of one measurement pass."""

    suites: dict[str, list[SuiteRun]] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)


def check_scorecard(suites: list[dict[str, Any]]) -> dict[str, Any]:
    """Point-in-time counts for the CI scorecard. Does not affect the verdict.

    ``unbaselined_tests`` counts collected tests above the baseline floor.
    A collection drop is not negative unbaselined work. ``unbaselined_rate``
    is that count divided by collected tests, or 0.0 when nothing was collected.
    """
    unbaselined = 0
    collected = 0
    seconds: dict[str, float] = {}
    for suite in suites:
        got = int(suite.get("collected", 0))
        floor = int(suite.get("baseline_collected", 0))
        collected += got
        unbaselined += max(0, got - floor)
        if "seconds" in suite:
            seconds[str(suite.get("name", ""))] = float(suite["seconds"])
    rate = (unbaselined / collected) if collected else 0.0
    return {
        "unbaselined_tests": unbaselined,
        "unbaselined_rate": rate,
        "suite_seconds": seconds,
    }


@dataclass
class Report:
    """The gate verdict. Serialized to JSON for agents and PR comments."""

    status: str = "pass"
    problems: list[Problem] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    suites: list[dict[str, Any]] = field(default_factory=list)
    metrics: list[dict[str, Any]] = field(default_factory=list)
    isolation: dict[str, dict[str, str]] = field(default_factory=dict)
    config_source: str = ""
    error: str = ""
    approval: dict[str, Any] | None = None
    approval_provenance: dict[str, Any] | None = None
    exit_code: int | None = None  # set for preflight failures (3); else derived from status

    def to_json(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "tool": "pawl",
            "version": __version__,
            "kind": "check",
            "status": self.status,
            "exit_code": self.exit_code
            if self.exit_code is not None
            else exit_code_for(self.status),
            "generated_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            "config_source": self.config_source,
            "approval": self.approval,
            "approval_provenance": self.approval_provenance,
            "error": self.error,
            "problems": [p.to_json() for p in self.problems],
            "notes": self.notes,
            "suites": self.suites,
            "metrics": self.metrics,
            "isolation": self.isolation,
            "scorecard": check_scorecard(self.suites),
            "next_steps": next_steps(self.problems),
        }


def _wanted(item: SuiteConfig | MetricConfig, ci: bool) -> bool:
    return ci or not item.ci_only


def measure_all(config: Config, ci: bool, orders: int | None = None) -> Measurement:
    """Run every suite (in the requested number of orders) and every metric."""
    m = Measurement()
    for suite in config.suites:
        if not _wanted(suite, ci):
            m.skipped.append(suite.name)
            continue
        count = orders if orders is not None else suite.check_orders
        m.suites[suite.name] = [run_suite(suite, config.root, i) for i in range(count)]
    for metric in config.metrics:
        if not _wanted(metric, ci):
            m.skipped.append(metric.name)
            continue
        m.metrics[metric.name] = measure(metric, config.root)
    return m


def _cap(ids: set[str] | list[str]) -> list[str]:
    return sorted(ids)


def compare_suite(
    suite: SuiteConfig,
    base: SuiteBaseline,
    runs: list[SuiteRun],
    quarantined: set[str],
    lock: bool,
) -> tuple[list[Problem], list[str], dict[str, Any]]:
    """Compare one suite. Returns (problems, notes, summary)."""
    problems: list[Problem] = []
    notes: list[str] = []
    main = runs[0]
    failing = main.failing - quarantined
    base_failing = set(base.failing_ids) - quarantined
    new = failing - base_failing
    fixed = base_failing - failing
    if base.identity == "ids":
        # A known failure that vanished is missing, not fixed.
        fixed = {t for t in fixed if main.outcomes.get(t) == "passed"}
        if new:
            problems.append(
                Problem(
                    "NEW_FAILURE",
                    suite.name,
                    f"{len(new)} test(s) fail that the baseline records as passing",
                    _cap(new),
                )
            )
        missing = set(base.collected_ids) - main.ids
        if missing:
            problems.append(
                Problem(
                    "MISSING_TESTS",
                    suite.name,
                    f"{len(missing)} test(s) in the baseline were not collected or did not run",
                    _cap(missing),
                )
            )
        newly_skipped = (main.skipped & set(base.collected_ids)) - set(base.skipped_ids)
        if newly_skipped:
            problems.append(
                Problem(
                    "NEWLY_SKIPPED",
                    suite.name,
                    f"{len(newly_skipped)} test(s) now skip that ran in the baseline",
                    _cap(newly_skipped),
                )
            )
    elif len(failing) > len(base_failing):
        problems.append(
            Problem(
                "NEW_FAILURE",
                suite.name,
                f"{len(failing)} failures exceed the baseline of {len(base_failing)}",
                _cap(failing),
            )
        )
    if main.collected < base.collected:
        problems.append(
            Problem(
                "COLLECTION_DROP",
                suite.name,
                f"{main.collected} tests collected, below the floor of {base.collected}. "
                "Tests that are never collected produce no failure line.",
            )
        )
    for alt in runs[1:]:
        od = (alt.failing - quarantined) - failing - set(base.order_dependent) - base_failing
        if od:
            problems.append(
                Problem(
                    "ORDER_DEPENDENT_FAILURE",
                    suite.name,
                    f"{len(od)} test(s) fail only in order '{alt.order}'",
                    _cap(od),
                )
            )
    if fixed:
        msg = (
            f"{len(fixed)} baseline failure(s) now pass. Run 'pawl update' and commit "
            "the tighter baseline in this change."
        )
        if lock:
            problems.append(Problem("STALE_BASELINE", suite.name, msg, _cap(fixed)))
        else:
            notes.append(f"{suite.name}: {msg}")
    if main.collected > base.collected:
        notes.append(
            f"{suite.name}: {main.collected - base.collected} new test(s) are not yet in the "
            "baseline; run 'pawl update' so they are protected."
        )
    summary = {
        "name": suite.name,
        "adapter": suite.adapter,
        "orders": [r.order for r in runs],
        "failures": len(failing),
        "baseline_failures": len(base_failing),
        "collected": main.collected,
        "baseline_collected": base.collected,
        "new_failures": _cap(new)[:MAX_LISTED],
        "fixed": _cap(fixed)[:MAX_LISTED],
        "quarantined": sorted(quarantined)[:MAX_LISTED],
        "seconds": round(sum(r.seconds for r in runs), 2),
        "exit_code": main.exit_code,
    }
    return problems, notes, summary


def compare(
    config: Config,
    baseline: Baseline,
    m: Measurement,
    lock: bool,
    today: dt.date | None = None,
) -> Report:
    """Compare a measurement with the baseline."""
    today = today or dt.date.today()
    report = Report(config_source=config.source)
    configured = {s.name for s in config.suites} | {x.name for x in config.metrics}
    for orphan in sorted((set(baseline.suites) | set(baseline.metrics)) - configured):
        report.problems.append(
            Problem(
                "SUITE_REMOVED",
                orphan,
                "the baseline tracks this suite or metric but the config no longer runs it",
            )
        )
    for q in baseline.quarantine:
        if not q.active(today):
            report.notes.append(
                f"quarantine expired for {q.test_id} ({q.expires}); it counts again"
            )
    for suite in config.suites:
        if suite.name not in m.suites:
            report.notes.append(f"{suite.name}: skipped (ci_only)")
            continue
        base = baseline.suites.get(suite.name)
        if base is None:
            report.problems.append(
                Problem("NOT_IN_BASELINE", suite.name, "no baseline entry; run 'pawl update'")
            )
            continue
        runs = m.suites[suite.name]
        quarantined = baseline.active_quarantine(suite.name, today)
        problems, notes, summary = compare_suite(suite, base, runs, quarantined, lock)
        report.problems += problems
        report.notes += notes
        report.suites.append(summary)
        new_ids = next((p.ids for p in problems if p.code == "NEW_FAILURE"), [])
        if new_ids and suite.isolate_max > 0:
            verdicts = isolate(suite, config.root, new_ids)
            if verdicts:
                report.isolation[suite.name] = verdicts
                alone = [k for k, v in verdicts.items() if v == "passes-alone"]
                if alone:
                    report.notes.append(
                        f"{suite.name}: {len(alone)} new failure(s) pass when run alone. "
                        "Suspect shared state or a concurrent run. This is a diagnostic only; "
                        "the gate stays red."
                    )
    for metric in config.metrics:
        if metric.name not in m.metrics:
            report.notes.append(f"{metric.name}: skipped (ci_only)")
            continue
        value = m.metrics[metric.name]
        base_metric = baseline.metrics.get(metric.name)
        if base_metric is None:
            report.problems.append(
                Problem("NOT_IN_BASELINE", metric.name, "no baseline entry; run 'pawl update'")
            )
            continue
        base_value = float(base_metric["value"])
        delta = metric_delta(metric, value, base_value)
        worse, better = delta == "worse", delta == "better"
        report.metrics.append(
            {
                "name": metric.name,
                "value": value,
                "baseline": base_value,
                "direction": metric.direction,
            }
        )
        if worse:
            report.problems.append(
                Problem(
                    "METRIC_REGRESSION",
                    metric.name,
                    f"{metric.name} is {value:g}, worse than the baseline {base_value:g} "
                    f"(may only go {metric.direction})",
                )
            )
        elif better:
            msg = f"{metric.name} improved to {value:g} from {base_value:g}; run 'pawl update'"
            if lock:
                report.problems.append(Problem("STALE_BASELINE", metric.name, msg))
            else:
                report.notes.append(msg)
    report.status = "fail" if report.problems else "pass"
    return report


_STEPS = {
    "NEW_FAILURE": (
        "Fix the code so the listed tests pass again. Do not edit, skip, or delete tests. "
        "If a test contradicts the specification, run 'pawl escalate' and stop."
    ),
    "MISSING_TESTS": (
        "Restore the missing tests or fix the collection error. Removing tests needs a "
        "human: 'pawl update --loosen --reason ...'."
    ),
    "NEWLY_SKIPPED": "Remove the new skip or xfail. Skipping a test needs human approval.",
    "COLLECTION_DROP": "Find why tests stopped being collected (import error, rename, config).",
    "ORDER_DEPENDENT_FAILURE": "Remove the shared state that makes these tests depend on order.",
    "METRIC_REGRESSION": "Bring the metric back to its baseline. Do not edit the baseline.",
    "STALE_BASELINE": "Run 'pawl update' and commit pawl.baseline.json with this change.",
    "NOT_IN_BASELINE": "A human runs 'pawl update' to record the new suite or metric.",
    "SUITE_REMOVED": "Restore the suite in pawl.toml. Removing a gate needs human approval.",
}


def next_steps(problems: list[Problem]) -> list[str]:
    seen: list[str] = []
    for p in problems:
        step = _STEPS.get(p.code)
        if step and step not in seen:
            seen.append(step)
    return seen


def suite_baseline_from_run(suite: SuiteConfig, run: SuiteRun) -> SuiteBaseline:
    return SuiteBaseline(
        failing_ids=sorted(run.failing),
        collected=run.collected,
        collected_ids=sorted(run.ids) if suite.identity == "ids" else [],
        skipped_ids=sorted(run.skipped) if suite.identity == "ids" else [],
        identity=suite.identity,
    )


def report_path(root: Path, name: str = "last-report.json") -> Path:
    d = root / ".pawl"
    d.mkdir(exist_ok=True)
    gitignore = d / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("last-*.json\nhook-state.json\n", encoding="utf-8")
    return d / name
