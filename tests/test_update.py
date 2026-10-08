from __future__ import annotations

import datetime as dt
from pathlib import Path

from pawl.adapters import SuiteRun
from pawl.baseline import Baseline, Quarantine, SuiteBaseline
from pawl.check import Measurement
from pawl.config import parse_config
from pawl.update import Delta, append_debt_log, compute

CFG = """
[[suite]]
name = "t"
adapter = "pytest"
command = "x"
[[metric]]
name = "lint"
command = "x"
direction = "down"
extract = "count-lines"
"""


def test_compute_classifies_changes(tmp_path: Path) -> None:
    cfg = parse_config(CFG, tmp_path)
    old = Baseline(
        suites={"t": SuiteBaseline(failing_ids=["a"], collected=3, collected_ids=["a", "b", "c"])},
        metrics={"lint": {"value": 5, "direction": "down"}},
        quarantine=[Quarantine("t", "q", "r", "2000-01-01")],
    )
    runs = [
        SuiteRun({"a": "passed", "b": "failed", "d": "passed"}),
        SuiteRun({"a": "passed", "b": "passed", "d": "passed"}, order="reverse"),
    ]
    m = Measurement(suites={"t": runs}, metrics={"lint": 2})
    new, delta = compute(cfg, old, m, dt.date(2026, 1, 1))
    loosened = "\n".join(delta.loosened)
    tightened = "\n".join(delta.tightened)
    assert "newly failing: b" in loosened
    assert "tests removed: c" in loosened
    assert "fixed: a" in tightened
    assert "lint: 5 -> 2" in tightened
    assert "quarantine expired" in tightened
    assert delta.order_dependent == {"t": ["b"]}
    assert new.suites["t"].confirmed_orders == 2
    assert new.quarantine == []


def test_first_update_records_everything(tmp_path: Path) -> None:
    cfg = parse_config(CFG, tmp_path)
    m = Measurement(suites={"t": [SuiteRun({"a": "passed"})]}, metrics={"lint": 1})
    new, delta = compute(cfg, None, m, dt.date(2026, 1, 1))
    assert not delta.loosened
    assert new.suites["t"].collected_ids == ["a"]


def test_debt_log_is_append_only(tmp_path: Path) -> None:
    log = tmp_path / "PAWL_DEBT.md"
    append_debt_log(log, "init", Delta(tightened=["t: recorded"]), "start")
    append_debt_log(log, "update", Delta(loosened=["t: newly failing: x"]), "upstream outage")
    text = log.read_text()
    assert text.startswith("# Pawl debt log")
    assert text.index("(tightened)") < text.index("(LOOSENED)")
    assert "Reason: upstream outage" in text
