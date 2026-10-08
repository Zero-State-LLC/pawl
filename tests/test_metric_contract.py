"""Metric contract: ok_exit_codes, cwd, tolerance. The F1 regression is in test_regressions.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from pawl.cli import main
from pawl.config import MetricConfig, parse_config
from pawl.errors import ConfigError, ParseError
from pawl.metrics import measure, metric_delta


def test_ok_exit_codes_allows_tools_that_exit_nonzero_on_findings(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    script = "print('E1')\nprint('E2')\nraise SystemExit(1)\n"
    (repo / "tool.py").write_text(script, encoding="utf-8")
    m = MetricConfig(
        "m", (sys.executable, "tool.py"), "down", "count-regex:^E", ok_exit_codes=(0, 1)
    )
    assert measure(m, repo) == 2
    with pytest.raises(ParseError, match="allowed: 0"):
        measure(MetricConfig("m", (sys.executable, "tool.py"), "down", "count-regex:^E"), repo)


def test_metric_cwd(tmp_path: Path) -> None:
    sub = tmp_path / "pkg"
    sub.mkdir()
    (sub / "data.txt").write_text("a\nb\nc\n", encoding="utf-8")
    code = "print(open('data.txt').read(), end='')"
    m = MetricConfig("m", (sys.executable, "-c", code), "down", "count-lines", cwd="pkg")
    assert measure(m, tmp_path) == 3


def test_tolerance() -> None:
    cov = MetricConfig("cov", ("x",), "up", "regex:(\\d+)", tolerance=0.05)
    assert metric_delta(cov, 85.78, 85.79) == "same"
    assert metric_delta(cov, 85.80, 85.79) == "same"
    assert metric_delta(cov, 85.70, 85.79) == "worse"
    assert metric_delta(cov, 85.90, 85.79) == "better"
    lint = MetricConfig("lint", ("x",), "down", "count-lines")
    assert metric_delta(lint, 3, 3) == "same"
    assert metric_delta(lint, 4, 3) == "worse"
    assert metric_delta(lint, 2, 3) == "better"


def test_tolerance_in_check_and_update(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "cov.txt").write_text("TOTAL 85.79\n", encoding="utf-8")
    (repo / "pawl.toml").write_text(
        "[[metric]]\n"
        'name = "coverage"\n'
        f'command = [{json.dumps(sys.executable)}, "-c", '
        "\"print(open('cov.txt').read())\"]\n"
        'direction = "up"\n'
        'extract = "regex:TOTAL (\\\\d+\\\\.\\\\d+)"\n'
        "tolerance = 0.05\n",
        encoding="utf-8",
    )
    assert main(["--root", str(repo), "update"]) == 0
    (repo / "cov.txt").write_text("TOTAL 85.81\n", encoding="utf-8")
    # A gain inside the tolerance is not STALE_BASELINE under --lock.
    assert main(["--root", str(repo), "check", "--lock"]) == 0
    assert main(["--root", str(repo), "update"]) == 0
    baseline = json.loads((repo / "pawl.baseline.json").read_text())
    assert baseline["metrics"]["coverage"]["value"] == 85.79
    (repo / "cov.txt").write_text("TOTAL 85.60\n", encoding="utf-8")
    assert main(["--root", str(repo), "check"]) == 1


@pytest.mark.parametrize(
    ("snippet", "message"),
    [
        ("ok_exit_codes = []", "ok_exit_codes"),
        ('ok_exit_codes = ["0"]', "ok_exit_codes"),
        ("tolerance = -1", "tolerance"),
        ('tolerance = "x"', "tolerance"),
        ("tolerance = nan", "tolerance"),
        ("tolerance = inf", "tolerance"),
    ],
)
def test_metric_config_validation(snippet: str, message: str) -> None:
    text = (
        '[[metric]]\nname = "m"\ncommand = ["x"]\ndirection = "down"\n'
        f'extract = "count-lines"\n{snippet}\n'
    )
    with pytest.raises(ConfigError, match=message):
        parse_config(text, Path("."))


def test_metric_config_defaults() -> None:
    text = '[[metric]]\nname = "m"\ncommand = ["x"]\ndirection = "down"\nextract = "count-lines"\n'
    metric = parse_config(text, Path(".")).metrics[0]
    assert metric.ok_exit_codes == (0,) and metric.cwd == "." and metric.tolerance == 0.0
