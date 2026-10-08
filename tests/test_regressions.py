"""Regression tests for bugs reproduced in the 2026-10-08 architecture review.

Each test here fails on pawl 0.1.1 (main 8fcac25) and passes with the fix. They
only use the command-line entry point, so they run unchanged against 0.1.1.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from pawl.cli import main

LINT = "import product\nfor i in range(product.N):\n    print('WARN finding', i)\n"


def _repo(tmp_path: Path, extract: str, extra: str = "") -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "lint.py").write_text(LINT, encoding="utf-8")
    (repo / "product.py").write_text("N = 3\n", encoding="utf-8")
    (repo / "pawl.toml").write_text(
        "[[metric]]\n"
        'name = "lint_findings"\n'
        f'command = [{json.dumps(sys.executable)}, "-B", "lint.py"]\n'
        'direction = "down"\n'
        f"extract = {json.dumps(extract)}\n" + extra,
        encoding="utf-8",
    )
    assert main(["--root", str(repo), "update"]) == 0
    return repo


@pytest.mark.parametrize("extract", ["count-regex:WARN", "count-lines"])
def test_crashed_metric_command_is_an_error_not_zero(tmp_path: Path, extract: str) -> None:
    repo = _repo(tmp_path, extract)
    (repo / "product.py").write_text("N = 50\nraise RuntimeError('boom')\n", encoding="utf-8")
    # On 0.1.1 this was exit 0 ("improved to 0 from 3"). It must fail closed.
    assert main(["--root", str(repo), "check"]) == 2
    report = json.loads((repo / ".pawl" / "last-report.json").read_text())
    assert report["status"] == "error"
    assert "exited 1" in report["error"]
    # And the crash must not be recordable as a tightening.
    assert main(["--root", str(repo), "update"]) == 2
    baseline = json.loads((repo / "pawl.baseline.json").read_text())
    assert baseline["metrics"]["lint_findings"]["value"] == 3


def test_real_regression_still_fails(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "count-regex:WARN")
    (repo / "product.py").write_text("N = 50  # more findings\n", encoding="utf-8")
    assert main(["--root", str(repo), "check"]) == 1
