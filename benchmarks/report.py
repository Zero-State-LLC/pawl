"""Write BENCHMARKS.md."""

from __future__ import annotations

import datetime as dt
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

from benchmarks.corpus import SCENARIOS
from benchmarks.effectiveness import DETECTOR_LABELS, DETECTORS, Result, score

ROOT = Path(__file__).resolve().parents[1]


def machine() -> dict[str, str]:
    def git(*args: str) -> str:
        done = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False)
        return done.stdout.strip() or "unknown"

    cpu = "unknown"
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    except OSError:
        cpu = platform.processor() or "unknown"
    # Benchmark outputs do not count as changes to the code under test.
    dirty = git(
        "status",
        "--porcelain",
        "--",
        ".",
        ":!BENCHMARKS.md",
        ":!benchmarks/results.json",
        ":!benchmarks/live_trial.md",
        ":!benchmarks/live_transcripts",
    )
    return {
        "date": dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z"),
        "commit": git("rev-parse", "--short=12", "HEAD")
        + (" (working tree has changes)" if dirty not in ("", "unknown") else ""),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "cpu": f"{cpu}, {os.cpu_count()} logical CPUs",
        "load": " / ".join(f"{x:.2f}" for x in os.getloadavg()),
    }


def _pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def effectiveness_md(results: list[Result]) -> str:
    lines = ["## A. Effectiveness", ""]
    errors = [r for r in results if r.error]
    for base, title in (
        ("clean", "Base with no known failures"),
        ("debt", "Base with one known failing test (debt)"),
    ):
        s = score(results, base)
        b = s[DETECTORS[0]]
        lines += [
            f"### {title}",
            "",
            f"{b['bad']} bad changes, {b['clean']} clean changes.",
            "",
            "| Detector | Recall (bad caught) | False positives (clean blocked) |",
            "| --- | --- | --- |",
        ]
        for d in DETECTORS:
            r = s[d]
            lines.append(
                f"| {DETECTOR_LABELS[d]} | {r['tp']}/{r['bad']} ({_pct(r['recall'])}) "
                f"| {r['fp']}/{r['clean']} ({_pct(r['fpr'])}) |"
            )
        lines.append("")
    lines += [
        "### Per scenario",
        "",
        "Y means the detector failed the change (exit code not 0). For bad changes Y is "
        "correct; for clean changes Y is a false positive.",
        "",
        "| Scenario | Base | Label | "
        + " | ".join(DETECTOR_LABELS[d] for d in DETECTORS)
        + " | Pawl CI signals |",
        "| --- | --- | --- | " + " | ".join("---" for _ in DETECTORS) + " | --- |",
    ]
    for r in sorted(results, key=lambda x: (x.label, x.scenario, x.base)):
        if r.error:
            continue
        marks = " | ".join("Y" if r.caught.get(d) else "-" for d in DETECTORS)
        label = r.label + (" (known miss)" if r.known_miss else "")
        sig = ", ".join(r.signals) or "none"
        lines.append(f"| {r.scenario} | {r.base} | {label} | {marks} | {sig} |")
    lines += ["", "### Scenario descriptions", ""]
    for s in SCENARIOS:
        lines.append(f"- `{s.name}` ({s.label}, {s.category}): {s.what}.")
    if errors:
        lines += ["", "### Scenarios that failed to run", ""]
        lines += [f"- {r.scenario} ({r.base}): {r.error}" for r in errors]
    return "\n".join(lines) + "\n"


def _fmt(t: dict[str, float]) -> str:
    return f"{t['median']:.2f} s ({t['min']:.2f} to {t['max']:.2f})"


def performance_md(perf: list[dict[str, Any]]) -> str:
    keys = [
        ("bare_pytest", "bare `pytest -q`"),
        ("bare_pytest_junit", "bare `pytest -q --junitxml`"),
        ("pawl_check_1_order", "`pawl check --orders 1`"),
        ("pawl_check_2_orders", "`pawl check --orders 2`"),
        ("pawl_guard", "`pawl guard` (one test file changed)"),
        ("pawl_guard_replay", "`pawl guard --replay` (one test file changed)"),
    ]
    n = perf[0][keys[0][0]]["n"]
    lines = [
        "## B. Performance",
        "",
        f"Median wall-clock time of {n} runs, with min to max in parentheses. Each test is a "
        "trivial assertion, so these numbers isolate Pawl's own overhead; on real suites test "
        "time dominates.",
        "",
        "| Command | " + " | ".join(f"{p['tests']} tests" for p in perf) + " |",
        "| --- | " + " | ".join("---" for _ in perf) + " |",
    ]
    for key, label in keys:
        lines.append(f"| {label} | " + " | ".join(_fmt(p[key]) for p in perf) + " |")
    pj = "parse JUnit XML in process"
    lines.append(
        f"| {pj} | "
        + " | ".join(f"{1000 * p['parse_junit_in_process']['median']:.1f} ms" for p in perf)
        + " |"
    )
    lines += ["", "Overhead of `pawl check --orders 1` over bare `pytest -q`:", ""]
    for p in perf:
        over = p["pawl_check_1_order"]["median"] - p["bare_pytest"]["median"]
        ratio = p["pawl_check_1_order"]["median"] / p["bare_pytest"]["median"]
        lines.append(f"- {p['tests']} tests: +{over:.2f} s ({ratio:.2f}x).")
    return "\n".join(lines) + "\n"


LIMITS = """## Limits of this benchmark

- The corpus is small and synthetic. Each bad change was written by hand to model one
  pattern reported in the literature (see RESEARCH.md). It measures whether each
  mechanism fires on the pattern it targets, not how often real agents use each pattern.
  Recall here is not a prediction of recall on real agent traffic.
- The corpus was written by the same author as Pawl, so it shares the author's blind
  spots. A third-party corpus (for example ImpossibleBench or EvilGenie transcripts)
  would be a fairer test. The live-agent trial below is a small step in that direction.
- One project, one language (Python and pytest). Adapters for Jest, Vitest, Go, Cargo
  and JUnit are covered by unit and end-to-end tests, not by this corpus.
- `special_case_no_holdout` is an expected miss: when the tests a change was graded on
  are the only oracle, hard-coding their inputs is undetectable by any test-based gate.
  A holdout suite, a mutation check, or human review is needed.
- The agent-side columns run in the agent's own environment. An agent with a shell can
  skip or disable them, so they are early feedback, not enforcement.
- "Pawl CI" assumes the CI job runs the trusted-ref check and the guard, the check is
  required, and CODEOWNERS protects the gate files. Without branch protection, Pawl in
  CI is advice, not a gate.
- The guard's suspicious-code patterns are regular expressions. They catch the common
  forms in the literature and miss obfuscated ones.
- The Abraxas column ports the ratchet logic faithfully (same grep, same floor, same
  preflight) to this demo. Abraxas also runs explicit file lists in CI; that is outside
  the script and not modeled.
- Performance uses synthetic suites of trivial tests, 100 per file; the largest is
  20000 tests. Suites with slow tests, heavy fixtures or many more files are not
  measured.
- Everything here ran on Linux. Pawl's own CI runs on macOS. Windows is untested.
- Performance was measured on a shared machine. The load average at the start of the
  run is listed above; treat small differences as noise.
"""


def write(
    results: list[Result] | None,
    perf: list[dict[str, Any]] | None,
    live: str = "",
    m: dict[str, str] | None = None,
) -> Path:
    m = m or machine()
    head = (
        [
            "# Benchmarks",
            "",
            "Generated by `python -m benchmarks run` (or `make bench`). Do not edit by hand; "
            "rerun the command.",
            "",
            "| | |",
            "| --- | --- |",
        ]
        + [f"| {k} | {v} |" for k, v in m.items()]
        + [""]
    )
    parts = ["\n".join(head)]
    if results is not None:
        parts.append(effectiveness_md(results))
    if perf is not None:
        parts.append(performance_md(perf))
    parts.append(LIMITS)
    if live:
        parts.append(live)
    path = ROOT / "BENCHMARKS.md"
    path.write_text("\n".join(parts), encoding="utf-8")
    return path
