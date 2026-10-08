"""Run every labeled scenario through four detectors and score them."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from benchmarks.corpus import DEBT_FIX, DEMO, SCENARIOS, Ctx, Scenario, bench_env

HERE = Path(__file__).resolve().parent
DETECTORS = (
    "plain_pytest",
    "abraxas_ratchet",
    "pawl_local",
    "pawl_stop_hook",
    "pawl_ci_no_holdout",
    "pawl_ci",
)
DETECTOR_LABELS = {
    "plain_pytest": "plain `pytest` passes",
    "abraxas_ratchet": "Abraxas test_ratchet.sh",
    "pawl_local": "`pawl check` (agent side)",
    "pawl_stop_hook": "`pawl hook stop --base` (agent side)",
    "pawl_ci_no_holdout": "Pawl CI without holdout",
    "pawl_ci": "Pawl CI (check + guard + holdout)",
}


@dataclass
class Result:
    scenario: str
    base: str
    label: str
    category: str
    known_miss: bool
    caught: dict[str, bool] = field(default_factory=dict)
    seconds: dict[str, float] = field(default_factory=dict)
    signals: list[str] = field(default_factory=list)
    error: str = ""


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=bench@example.com", "-c", "user.name=bench", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def _run(cmd: list[str], cwd: Path, env: dict[str, str]) -> tuple[int, str, float]:
    start = time.perf_counter()
    done = subprocess.run(
        cmd, cwd=cwd, env=env, capture_output=True, text=True, check=False, timeout=600
    )
    return done.returncode, done.stdout, time.perf_counter() - start


def prepare(work: Path, base: str) -> Ctx:
    repo = work / "repo"
    shutil.copytree(DEMO, repo, ignore=shutil.ignore_patterns("__pycache__", ".pawl", "*.pyc"))
    tmpl = (HERE / "abraxas_ratchet.sh.tmpl").read_text(encoding="utf-8")
    failures = 1 if base == "debt" else 0
    (repo / "scripts").mkdir()
    (repo / "scripts" / "test_ratchet.sh").write_text(
        tmpl.replace("@FAILURES@", str(failures)).replace("@COLLECTED@", "10"), encoding="utf-8"
    )
    ctx = Ctx(repo, work)
    if base == "clean":
        ctx.edit("calc/__init__.py", *DEBT_FIX)
        if ctx.pawl("update") != 0:
            raise RuntimeError("could not tighten the clean base")
    for cache in repo.rglob("__pycache__"):
        shutil.rmtree(cache)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "checkout", "-qb", "agent")
    return ctx


def evaluate(scenario: Scenario, base: str) -> Result:
    res = Result(scenario.name, base, scenario.label, scenario.category, scenario.known_miss)
    with tempfile.TemporaryDirectory(prefix="pawl-bench-") as tmp:
        try:
            ctx = prepare(Path(tmp), base)
            scenario.apply(ctx)
            _git(ctx.repo, "add", "-A")
            _git(ctx.repo, "commit", "-qm", "agent change", "--allow-empty")
            env = bench_env(ctx.env)
            repo = ctx.repo
            py = sys.executable
            rc, _, s = _run(
                [py, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"], repo, env
            )
            res.caught["plain_pytest"], res.seconds["plain_pytest"] = rc != 0, s
            rc, _, s = _run(["bash", "scripts/test_ratchet.sh"], repo, env)
            res.caught["abraxas_ratchet"], res.seconds["abraxas_ratchet"] = rc != 0, s
            pawl = [py, "-m", "pawl", "--root", str(repo)]
            rc, _, s = _run([*pawl, "check"], repo, env)
            res.caught["pawl_local"], res.seconds["pawl_local"] = rc != 0, s
            start = time.perf_counter()
            hook = subprocess.run(
                [*pawl, "hook", "stop", "--format", "codex", "--base", "main"],
                cwd=repo,
                env=env,
                input="{}",
                capture_output=True,
                text=True,
                check=False,
            )
            res.seconds["pawl_stop_hook"] = time.perf_counter() - start
            res.caught["pawl_stop_hook"] = '"decision": "block"' in hook.stdout
            crc, cout, s1 = _run(
                [*pawl, "check", "--ci", "--trusted-ref", "main", "--json"], repo, env
            )
            grc, gout, s2 = _run(
                [*pawl, "guard", "--ci", "--replay", "--base", "main", "--json"], repo, env
            )
            res.seconds["pawl_ci"] = s1 + s2
            check = json.loads(cout) if cout.strip().startswith("{") else {"status": "error"}
            guard = json.loads(gout) if gout.strip().startswith("{") else {"status": "error"}
            problems = check.get("problems", [])
            res.signals += [f"check:{p['code']}({p['subject']})" for p in problems]
            if check.get("status") == "error":
                res.signals.append(f"check:ERROR exit {crc}")
            res.signals += sorted(
                {
                    f"guard:{f['rule']}"
                    for f in guard.get("findings", [])
                    if f.get("severity") == "block"
                }
            )
            if guard.get("status") == "error":
                res.signals.append(f"guard:ERROR exit {grc}")
            res.caught["pawl_ci"] = crc != 0 or grc != 0
            non_holdout = [p for p in problems if p.get("subject") != "holdout"]
            res.caught["pawl_ci_no_holdout"] = (
                grc != 0 or check.get("status") == "error" or bool(non_holdout)
            )
            res.seconds["pawl_ci_no_holdout"] = res.seconds["pawl_ci"]
        except Exception as exc:
            res.error = f"{type(exc).__name__}: {exc}"
    return res


def run_all(workers: int = 4) -> list[Result]:
    jobs = [(s, b) for s in SCENARIOS for b in s.bases]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda j: evaluate(*j), jobs))


def score(results: list[Result], base: str | None = None) -> dict[str, dict[str, Any]]:
    rows = [r for r in results if not r.error and (base is None or r.base == base)]
    out: dict[str, dict[str, Any]] = {}
    for d in DETECTORS:
        bad = [r for r in rows if r.label == "bad"]
        clean = [r for r in rows if r.label == "clean"]
        tp = sum(r.caught.get(d, False) for r in bad)
        fp = sum(r.caught.get(d, False) for r in clean)
        out[d] = {
            "tp": tp,
            "bad": len(bad),
            "fp": fp,
            "clean": len(clean),
            "recall": tp / len(bad) if bad else 0.0,
            "fpr": fp / len(clean) if clean else 0.0,
        }
    return out
