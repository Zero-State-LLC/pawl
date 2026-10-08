"""Write the baseline. Tightening is free; loosening needs --loosen and a reason."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

from pawl.adapters import SuiteRun
from pawl.baseline import Baseline, SuiteBaseline
from pawl.check import Measurement, suite_baseline_from_run
from pawl.config import Config, SuiteConfig
from pawl.metrics import metric_delta

DEBT_HEADER = """# Pawl debt log

Append-only record of every baseline change, newest last. Pawl writes this
file. A human reviews every entry marked LOOSENED.
"""


@dataclass
class Delta:
    """What an update would change."""

    tightened: list[str] = field(default_factory=list)
    loosened: list[str] = field(default_factory=list)
    order_dependent: dict[str, list[str]] = field(default_factory=dict)


def default_orders(suite: SuiteConfig) -> int:
    """Baselines are confirmed under two orders when the runner supports it."""
    return 2 if suite.adapter == "pytest" or suite.order_args else 1


def _order_dependent(runs: list[SuiteRun]) -> list[str]:
    main = runs[0].failing
    od: set[str] = set()
    for alt in runs[1:]:
        od |= main ^ alt.failing
    return sorted(od)


def _short(ids: set[str] | list[str], limit: int = 8) -> str:
    items = sorted(ids)
    more = f" (+{len(items) - limit} more)" if len(items) > limit else ""
    return ", ".join(items[:limit]) + more


def compute(
    config: Config, old: Baseline | None, m: Measurement, today: dt.date
) -> tuple[Baseline, Delta]:
    """Build the new baseline from a measurement and classify every change."""
    new = Baseline()
    delta = Delta()
    old = old or Baseline()
    for suite in config.suites:
        runs = m.suites.get(suite.name)
        prev = old.suites.get(suite.name)
        if runs is None:
            if prev is not None:
                new.suites[suite.name] = prev  # ci_only suite not measured locally
            continue
        sb = suite_baseline_from_run(suite, runs[0])
        sb.confirmed_orders = len(runs)
        sb.order_dependent = _order_dependent(runs)
        if sb.order_dependent:
            delta.order_dependent[suite.name] = sb.order_dependent
        new.suites[suite.name] = sb
        if prev is None:
            delta.tightened.append(
                f"{suite.name}: recorded {sb.failures} failing, {sb.collected} collected "
                f"({sb.confirmed_orders} order(s))"
            )
            continue
        _classify_suite(suite.name, prev, sb, delta)
    for metric in config.metrics:
        prev_m = old.metrics.get(metric.name)
        if metric.name not in m.metrics:
            if prev_m is not None:
                new.metrics[metric.name] = prev_m
            continue
        value = m.metrics[metric.name]
        if prev_m is None:
            new.metrics[metric.name] = {"value": value, "direction": metric.direction}
            delta.tightened.append(f"{metric.name}: recorded {value:g}")
            continue
        before = float(prev_m["value"])
        change = metric_delta(metric, value, before)
        if change == "same" and prev_m.get("direction") == metric.direction:
            new.metrics[metric.name] = prev_m  # within tolerance: keep the recorded value
            continue
        new.metrics[metric.name] = {"value": value, "direction": metric.direction}
        if prev_m.get("direction") != metric.direction:
            delta.loosened.append(
                f"{metric.name}: direction changed {prev_m.get('direction')} -> {metric.direction}"
            )
            continue
        worse = change == "worse"
        line = f"{metric.name}: {before:g} -> {value:g}"
        (delta.loosened if worse else delta.tightened).append(line)
    configured = {s.name for s in config.suites} | {x.name for x in config.metrics}
    for name in sorted((set(old.suites) | set(old.metrics)) - configured):
        delta.loosened.append(f"{name}: removed from the gate")
    for q in old.quarantine:
        if q.active(today):
            new.quarantine.append(q)
        else:
            delta.tightened.append(f"quarantine expired and removed: {q.test_id}")
    return new, delta


def _classify_suite(name: str, prev: SuiteBaseline, cur: SuiteBaseline, delta: Delta) -> None:
    added_fail = set(cur.failing_ids) - set(prev.failing_ids)
    fixed = set(prev.failing_ids) - set(cur.failing_ids)
    if added_fail:
        delta.loosened.append(f"{name}: newly failing: {_short(added_fail)}")
    if fixed:
        delta.tightened.append(f"{name}: fixed: {_short(fixed)}")
    if cur.collected < prev.collected:
        delta.loosened.append(f"{name}: collected {prev.collected} -> {cur.collected}")
    elif cur.collected > prev.collected:
        delta.tightened.append(f"{name}: collected {prev.collected} -> {cur.collected}")
    if prev.identity == "ids" and cur.identity == "ids":
        removed = set(prev.collected_ids) - set(cur.collected_ids)
        if removed:
            delta.loosened.append(f"{name}: tests removed: {_short(removed)}")
        skipped = (set(cur.skipped_ids) & set(prev.collected_ids)) - set(prev.skipped_ids)
        if skipped:
            delta.loosened.append(f"{name}: newly skipped: {_short(skipped)}")
    if prev.identity == "ids" and cur.identity == "count":
        delta.loosened.append(f"{name}: identity changed from ids to count")


def append_debt_log(path: Path, title: str, delta: Delta, reason: str | None) -> None:
    """Append a dated entry. Creates the file with a header if needed."""
    lines = [] if path.exists() else [DEBT_HEADER]
    stamp = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    kind = "LOOSENED" if delta.loosened else "tightened"
    lines.append(f"\n## {stamp}: {title} ({kind})\n")
    if reason:
        lines.append(f"- Reason: {reason}")
    for item in delta.loosened:
        lines.append(f"- LOOSENED {item}")
    for item in delta.tightened:
        lines.append(f"- tightened {item}")
    for suite, ids in delta.order_dependent.items():
        lines.append(f"- order-dependent in {suite}: {_short(ids)}")
    with path.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
