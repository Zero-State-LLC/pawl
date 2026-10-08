"""Wall-clock cost of Pawl on synthetic pytest suites."""

from __future__ import annotations

import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from benchmarks.corpus import bench_env

PER_FILE = 100


def make_project(root: Path, tests: int) -> None:
    (root / "tests").mkdir(parents=True)
    for f in range(tests // PER_FILE):
        body = "".join(
            f"def test_{f}_{i}():\n    assert {i} + 1 > {i}\n\n\n" for i in range(PER_FILE)
        )
        (root / "tests" / f"test_mod{f:03d}.py").write_text(body, encoding="utf-8")
    (root / "pawl.toml").write_text(
        '[[suite]]\nname = "tests"\nadapter = "pytest"\n'
        'command = ["python", "-m", "pytest", "tests", "-q"]\n',
        encoding="utf-8",
    )
    (root / ".gitignore").write_text(".pawl/\n__pycache__/\n", encoding="utf-8")


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=b@example.com", "-c", "user.name=b", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def _time(cmd: list[str], cwd: Path, runs: int, ok: tuple[int, ...] = (0,)) -> dict[str, float]:
    env = bench_env()
    samples = []
    for _ in range(runs):
        start = time.perf_counter()
        done = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, check=False)
        samples.append(time.perf_counter() - start)
        if done.returncode not in ok:
            raise RuntimeError(
                f"{cmd} exited {done.returncode}: {done.stdout[-500:]}{done.stderr[-500:]}"
            )
    return {
        "median": statistics.median(samples),
        "min": min(samples),
        "max": max(samples),
        "n": runs,
    }


def measure(tests: int, runs: int) -> dict[str, Any]:
    from pawl.adapters import parse_junit

    py = sys.executable
    with tempfile.TemporaryDirectory(prefix="pawl-perf-") as tmp:
        root = Path(tmp)
        make_project(root, tests)
        pawl = [py, "-m", "pawl", "--root", str(root)]
        subprocess.run(
            [*pawl, "update", "--orders", "1"], env=bench_env(), check=True, capture_output=True
        )
        _git(root, "init", "-q", "-b", "main")
        _git(root, "add", "-A")
        _git(root, "commit", "-qm", "base")
        _git(root, "checkout", "-qb", "agent")
        first = root / "tests" / "test_mod000.py"
        first.write_text(first.read_text().replace("assert 0 + 1 > 0", "assert 0 + 2 > 0"))
        out: dict[str, Any] = {"tests": tests}
        out["bare_pytest"] = _time(
            [py, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"], root, runs
        )
        out["bare_pytest_junit"] = _time(
            [
                py,
                "-m",
                "pytest",
                "tests",
                "-q",
                "-p",
                "no:cacheprovider",
                "-o",
                "junit_family=xunit1",
                "--junitxml",
                str(root / "j.xml"),
            ],
            root,
            runs,
        )
        out["pawl_check_1_order"] = _time(
            [*pawl, "check", "--orders", "1", "--skip-preflight"], root, runs
        )
        out["pawl_check_2_orders"] = _time(
            [*pawl, "check", "--orders", "2", "--skip-preflight"], root, runs
        )
        out["pawl_guard"] = _time([*pawl, "guard", "--base", "main"], root, runs, ok=(0, 1))
        out["pawl_guard_replay"] = _time(
            [*pawl, "guard", "--base", "main", "--replay"], root, runs, ok=(0, 1)
        )
        samples = []
        for _ in range(max(runs, 5)):
            start = time.perf_counter()
            parsed = parse_junit(root / "j.xml", pytest_ids=True)
            samples.append(time.perf_counter() - start)
        assert len(parsed) == tests, (len(parsed), tests)
        out["parse_junit_in_process"] = {
            "median": statistics.median(samples),
            "min": min(samples),
            "max": max(samples),
            "n": len(samples),
        }
    return out


def run_all(sizes: tuple[int, ...] = (100, 5000), runs: int = 5) -> list[dict[str, Any]]:
    return [measure(n, runs) for n in sizes]
