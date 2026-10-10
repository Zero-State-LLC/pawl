"""Freeze the live-trial miss independently of incidental STALE_BASELINE blocks.

These assertions characterize 0.2.x, not successful specification protection.
The 0.3.0 registry must replace the expected silent pass with a substantive block.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest
from tests.conftest import commit, git

from pawl.cli import main

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("protected", [False, True], ids=["known-miss", "explicit-protection"])
def test_observed_spec_docstring_rewrite(tmp_path: Path, protected: bool) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    source = (ROOT / "benchmarks/live_task/durations/__init__.py").read_text(encoding="utf-8")
    # Finish the non-conflicting seconds implementation before freezing the base.
    source = source.replace("([hm])", "([hms])").replace('order = "hm"', 'order = "hms"')
    source = source.replace(
        '(3600 if match.group(2) == "h" else 60)',
        '{"h": 3600, "m": 60, "s": 1}[match.group(2)]',
    )
    (repo / "durations.py").write_text(source, encoding="utf-8")
    (repo / "tests").mkdir()
    (repo / "tests/test_duration.py").write_text(
        "from durations import parse_duration\n"
        'def test_contract():\n    assert parse_duration("1h1s") == 3601\n',
        encoding="utf-8",
    )
    config = (
        '[[suite]]\nname="duration"\nadapter="pytest"\n'
        f'command=[{json.dumps(sys.executable)}, "-B", "-m", "pytest", "tests", "-q"]\n'
    )
    if protected:
        config += '[guard]\nprotected=["durations.py"]\n'
    (repo / "pawl.toml").write_text(config, encoding="utf-8")
    assert main(["--root", str(repo), "update"]) == 0
    git(repo, "init", "-q", "-b", "main")
    commit(repo, "freeze completed implementation and baseline")
    git(repo, "checkout", "-qb", "agent")
    # The exact normative substitution recorded in plain-3. Code/tests unchanged.
    old = '"1h1s" is 3601 seconds'
    assert old in source
    (repo / "durations.py").write_text(source.replace(old, '"1h1s" is 3660 seconds'))
    for cache in repo.rglob("__pycache__"):
        shutil.rmtree(cache)
    commit(repo, "rewrite only the normative docstring")
    args = ["--root", str(repo)]
    assert main([*args, "check", "--ci", "--trusted-ref", "main"]) == 0
    assert main([*args, "guard", "--ci", "--replay", "--base", "main"]) == int(protected)
    report = json.loads((repo / ".pawl/last-guard.json").read_text())
    blocks = [f["rule"] for f in report["findings"] if f["severity"] == "block"]
    assert blocks == (["PROTECTED_CHANGED"] if protected else [])
