"""Turn runner output into per-test outcomes. Every adapter fails closed.

An adapter raises ParseError when the output cannot be read with confidence:
a missing report file, a runner crash, or counts that do not reconcile. A
gate that guesses is not a gate (UTBoost found log-parser annotation errors in
54% of SWE-bench Verified instances: https://arxiv.org/abs/2506.09289).
"""

from __future__ import annotations

import contextlib
import json
import re
import shutil
import stat
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from pawl.config import SuiteConfig
from pawl.errors import ParseError
from pawl.runner import run

PLUGIN_MODULE = "_pawl_pytest_order"
PLUGIN_SOURCE = '''"""Pawl test-order plugin. Loaded only for alternate-order runs."""
import os
import random


def pytest_collection_modifyitems(session, config, items):
    mode = os.environ.get("PAWL_TEST_ORDER", "")
    if mode == "reverse":
        items.reverse()
    elif mode.startswith("random:"):
        random.Random(int(mode.split(":", 1)[1])).shuffle(items)
'''


@dataclass
class SuiteRun:
    """Outcome of one suite run, keyed by stable test IDs."""

    outcomes: dict[str, str] = field(default_factory=dict)  # id -> passed|failed|skipped
    exit_code: int = 0
    seconds: float = 0.0
    tail: str = ""
    order: str = "default"

    @property
    def collected(self) -> int:
        return len(self.outcomes)

    @property
    def failing(self) -> set[str]:
        return {k for k, v in self.outcomes.items() if v == "failed"}

    @property
    def skipped(self) -> set[str]:
        return {k for k, v in self.outcomes.items() if v == "skipped"}

    @property
    def ids(self) -> set[str]:
        return set(self.outcomes)


def _record(outcomes: dict[str, str], test_id: str, outcome: str) -> None:
    # A test can report more than once (for example a call failure and a
    # teardown error). The worst outcome wins: failed > skipped > passed.
    rank = {"passed": 0, "skipped": 1, "failed": 2}
    prev = outcomes.get(test_id)
    if prev is None or rank[outcome] > rank[prev]:
        outcomes[test_id] = outcome


def _require_regular_report(path: Path, kind: str = "JUnit") -> None:
    """Refuse symlinks, hard links, and non-regular files before parsing a report.

    Same-user forged reports remain possible by overwriting a regular file in
    place; that needs a supervisor receipt (see docs/CI_TRUST_REVIEW.md). Links
    are a cheap false-PASS path and are rejected here.
    """
    if path.is_symlink():
        raise ParseError(f"{kind} report must be a regular file, not a symlink: {path}")
    try:
        st = path.lstat()
    except OSError as exc:
        raise ParseError(f"{kind} report not written: {path}") from exc
    if not stat.S_ISREG(st.st_mode):
        raise ParseError(f"{kind} report must be a regular file: {path}")
    if st.st_nlink > 1:
        raise ParseError(f"{kind} report must not be a hard link: {path}")


def parse_junit(path: Path, pytest_ids: bool = False) -> dict[str, str]:
    """Parse a JUnit XML file into ``{test_id: outcome}``."""
    if not path.exists():
        raise ParseError(f"JUnit report not written: {path}")
    _require_regular_report(path)
    try:
        # The report is written by the local test run; expat (2.4+) refuses entity
        # expansion attacks, and Pawl must stay stdlib-only.
        tree = ET.parse(path)  # noqa: S314
    except ET.ParseError as exc:
        raise ParseError(f"JUnit report is not valid XML: {exc}") from exc
    root = tree.getroot()
    if root.tag not in ("testsuite", "testsuites"):
        raise ParseError(f"JUnit report has an unsupported root: {root.tag}")
    # Summaries are optional, but when present they must agree with the cases.
    # Count XML records here, not deduplicated IDs: pytest may emit a passing
    # call followed by a teardown error for the same ID.
    for summary in root.iter():
        if summary.tag not in ("testsuite", "testsuites"):
            continue
        cases = list(summary.iter("testcase"))
        for attr, tag in (("failures", "failure"), ("errors", "error"), ("skipped", "skipped")):
            claimed = summary.get(attr)
            if claimed is None:
                continue
            if not re.fullmatch(r"[0-9]+", claimed):
                raise ParseError(f"JUnit {attr} summary is not a nonnegative integer")
            measured = sum(case.find(tag) is not None for case in cases)
            if (claimed.lstrip("0") or "0") != str(measured):
                raise ParseError(f"JUnit {attr} summary reports {claimed}, parsed {measured}")
    outcomes: dict[str, str] = {}
    for case in root.iter("testcase"):
        classname = case.get("classname", "")
        name = case.get("name", "")
        if not name.strip():
            raise ParseError("JUnit testcase has no nonempty name")
        if case.find("failure") is not None or case.find("error") is not None:
            outcome = "failed"
        elif case.find("skipped") is not None:
            outcome = "skipped"
        else:
            outcome = "passed"
        if pytest_ids:
            if not case.get("file") and outcome != "failed":
                # xunit2 reports drop the file attribute; IDs would collapse.
                raise ParseError(
                    "JUnit testcase has no file attribute; run pytest with -o junit_family=xunit1"
                )
            test_id = _pytest_nodeid(classname, name, case.get("file"))
        else:
            test_id = f"{classname}::{name}" if classname else name
        _record(outcomes, test_id, outcome)
    return outcomes


def _pytest_nodeid(classname: str, name: str, file: str | None) -> str:
    if not file:
        # Collection errors have no file attribute; keep them visible and stable.
        return f"<collect>::{classname or name}"
    module = file[:-3].replace("/", ".").replace("\\", ".") if file.endswith(".py") else file
    rest = classname[len(module) + 1 :] if classname.startswith(module + ".") else ""
    parts = [file] + ([p for p in rest.split(".") if p] if rest else []) + [name]
    return "::".join(parts)


_PYTEST_SUMMARY = re.compile(r"(\d+) (failed|errors?)\b")


def _pytest(suite: SuiteConfig, root: Path, order: str, extra: Sequence[str]) -> SuiteRun:
    with tempfile.TemporaryDirectory(prefix="pawl-") as tmp:
        report = Path(tmp) / "junit.xml"
        rootdir = (
            []
            if any(a.startswith("--rootdir") for a in suite.command)
            else [f"--rootdir={(root / suite.cwd).resolve()}"]
        )
        argv = (
            list(suite.command)
            + list(extra)
            + rootdir
            + [
                f"--junitxml={report}",
                "-o",
                "junit_family=xunit1",
                "-p",
                "no:cacheprovider",
            ]
        )
        env: dict[str, str] = {}
        if order != "default":
            (Path(tmp) / f"{PLUGIN_MODULE}.py").write_text(PLUGIN_SOURCE, encoding="utf-8")
            import os

            existing = os.environ.get("PYTHONPATH", "")
            env["PYTHONPATH"] = tmp + (os.pathsep + existing if existing else "")
            env["PAWL_TEST_ORDER"] = order
            argv += ["-p", PLUGIN_MODULE]
        done = run(argv, root / suite.cwd, suite.timeout, env)
        if done.returncode not in (0, 1, 2, 5):
            raise ParseError(
                f"pytest exited {done.returncode} (internal, usage, or abnormal exit):\n"
                f"{done.tail()}"
            )
        if not report.is_file():
            raise ParseError(f"pytest wrote no JUnit report. Runner output:\n{done.tail()}")
        outcomes = parse_junit(report, pytest_ids=True)
    failing = sum(1 for v in outcomes.values() if v == "failed")
    if done.returncode == 5 and outcomes:
        raise ParseError("pytest exited 5 (no tests collected) but the report lists test cases")
    if done.returncode == 0 and failing:
        raise ParseError("pytest exited 0 but the report lists failures; refusing to guess")
    if done.returncode in (1, 2) and not failing:
        raise ParseError(
            f"pytest exited {done.returncode} but no failure was parsed:\n{done.tail()}"
        )
    claimed = sum(int(n) for n, _ in _PYTEST_SUMMARY.findall(done.tail(3)))
    if claimed and not failing:
        raise ParseError("pytest summary reports failures that the report does not list")
    return SuiteRun(outcomes, done.returncode, done.seconds, done.tail(), order)


def _junit(suite: SuiteConfig, root: Path, order: str, extra: Sequence[str]) -> SuiteRun:
    assert suite.junit_path is not None
    report = root / suite.cwd / suite.junit_path
    if report.exists():
        report.unlink()  # never read a stale report
    done = run(list(suite.command) + list(extra), root / suite.cwd, suite.timeout)
    outcomes = parse_junit(report)
    failing = sum(1 for v in outcomes.values() if v == "failed")
    if done.returncode != 0 and not failing:
        raise ParseError(
            f"runner exited {done.returncode} but no failure was parsed:\n{done.tail()}"
        )
    if done.returncode == 0 and failing:
        raise ParseError("runner exited 0 but the JUnit report lists failures")
    return SuiteRun(outcomes, done.returncode, done.seconds, done.tail(), order)


def parse_jest_json(data: object, root: Path) -> dict[str, str]:
    """Parse Jest or Vitest ``--json`` output."""
    if not isinstance(data, dict) or "testResults" not in data:
        raise ParseError("jest/vitest JSON has no testResults")
    outcomes: dict[str, str] = {}
    for suite in data["testResults"]:
        file = str(suite.get("name", suite.get("testFilePath", "?")))
        with contextlib.suppress(ValueError):
            file = str(Path(file).resolve().relative_to(root.resolve()))
        assertions = suite.get("assertionResults", [])
        if suite.get("status") == "failed" and not assertions:
            _record(outcomes, f"{file}::<suite>", "failed")
        for a in assertions:
            status = a.get("status")
            test_id = f"{file}::{a.get('fullName') or a.get('title')}"
            if status == "passed":
                _record(outcomes, test_id, "passed")
            elif status == "failed":
                _record(outcomes, test_id, "failed")
            elif status in ("pending", "skipped", "todo", "disabled"):
                _record(outcomes, test_id, "skipped")
            else:
                raise ParseError(f"unknown jest status {status!r} for {test_id}")
    claimed = data.get("numFailedTests")
    counted = sum(1 for k, v in outcomes.items() if v == "failed" and not k.endswith("::<suite>"))
    if isinstance(claimed, int) and claimed != counted:
        raise ParseError(f"jest reports {claimed} failed tests but {counted} were parsed")
    return outcomes


def _jest(suite: SuiteConfig, root: Path, order: str, extra: Sequence[str]) -> SuiteRun:
    with tempfile.TemporaryDirectory(prefix="pawl-") as tmp:
        out = Path(tmp) / "report.json"
        flags = (
            ["--json", f"--outputFile={out}"]
            if suite.adapter == "jest"
            else ["--reporter=json", f"--outputFile={out}"]
        )
        done = run(list(suite.command) + list(extra) + flags, root / suite.cwd, suite.timeout)
        if not out.is_file():
            raise ParseError(f"{suite.adapter} did not write its JSON report:\n{done.tail()}")
        try:
            data = json.loads(out.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ParseError(f"{suite.adapter} JSON report is invalid: {exc}") from exc
    outcomes = parse_jest_json(data, root / suite.cwd)
    if done.returncode != 0 and not any(v == "failed" for v in outcomes.values()):
        raise ParseError(f"{suite.adapter} exited {done.returncode} with no parsed failure")
    return SuiteRun(outcomes, done.returncode, done.seconds, done.tail(), order)


def parse_go_json(text: str) -> dict[str, str]:
    """Parse ``go test -json`` event lines."""
    outcomes: dict[str, str] = {}
    seen_any = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ParseError(f"go test -json line is not JSON: {line[:80]}") from exc
        seen_any = True
        action = event.get("Action")
        pkg = event.get("Package", "?")
        test = event.get("Test")
        if action not in ("pass", "fail", "skip"):
            continue
        outcome = {"pass": "passed", "fail": "failed", "skip": "skipped"}[action]
        if test:
            _record(outcomes, f"{pkg}::{test}", outcome)
        elif action == "fail":
            # Package-level failure: build error or a failure outside any test.
            _record(outcomes, f"{pkg}::<package>", "failed")
    if not seen_any:
        raise ParseError("go test produced no -json events")
    return outcomes


def _go(suite: SuiteConfig, root: Path, order: str, extra: Sequence[str]) -> SuiteRun:
    argv = list(suite.command)
    if "-json" not in argv:
        argv.insert(2 if argv[:2] == ["go", "test"] else len(argv), "-json")
    done = run(argv + list(extra), root / suite.cwd, suite.timeout)
    outcomes = parse_go_json(done.stdout)
    if done.returncode != 0 and not any(v == "failed" for v in outcomes.values()):
        raise ParseError(f"go test exited {done.returncode} with no parsed failure:\n{done.tail()}")
    return SuiteRun(outcomes, done.returncode, done.seconds, done.tail(), order)


_CARGO_LINE = re.compile(r"^test (.+?) \.\.\. (ok|FAILED|ignored)\s*$")
_CARGO_RESULT = re.compile(
    r"^test result: \w+\. (\d+) passed; (\d+) failed; (\d+) ignored; \d+ measured; \d+ filtered out"
)


def parse_cargo(text: str) -> dict[str, str]:
    """Parse libtest output from ``cargo test``. Per-test lines must match summaries."""
    outcomes: dict[str, str] = {}
    lines = {"passed": 0, "failed": 0, "skipped": 0}
    totals = [0, 0, 0]
    saw_result = False
    binary = "?"
    for raw in text.splitlines():
        if raw.strip().startswith("Running ") or raw.strip().startswith("Doc-tests "):
            binary = raw.strip().split(" ", 1)[1].split(" (")[0]
        m = _CARGO_LINE.match(raw)
        if m:
            outcome = {"ok": "passed", "FAILED": "failed", "ignored": "skipped"}[m.group(2)]
            _record(outcomes, f"{binary}::{m.group(1)}", outcome)
            lines[outcome] += 1
            continue
        r = _CARGO_RESULT.match(raw.strip())
        if r:
            saw_result = True
            for i in range(3):
                totals[i] += int(r.group(i + 1))
    if not saw_result:
        raise ParseError("cargo test printed no 'test result:' line (build failure?)")
    if [lines["passed"], lines["failed"], lines["skipped"]] != totals:
        raise ParseError(f"cargo per-test lines {lines} do not match summaries {totals}")
    return outcomes


def _cargo(suite: SuiteConfig, root: Path, order: str, extra: Sequence[str]) -> SuiteRun:
    done = run(list(suite.command) + list(extra), root / suite.cwd, suite.timeout)
    outcomes = parse_cargo(done.output)
    if done.returncode != 0 and not any(v == "failed" for v in outcomes.values()):
        raise ParseError(f"cargo test exited {done.returncode} with no parsed failure")
    return SuiteRun(outcomes, done.returncode, done.seconds, done.tail(), order)


def order_extra(suite: SuiteConfig, index: int) -> tuple[str, list[str]]:
    """Return (order label, extra args) for the ``index``-th order of a suite."""
    if index == 0:
        return "default", []
    if suite.adapter == "pytest":
        return ("reverse" if index == 1 else f"random:{index}"), []
    if index - 1 < len(suite.order_args):
        return f"variant-{index}", list(suite.order_args[index - 1])
    raise ParseError(f"suite {suite.name}: no order variant #{index}; add order_args in pawl.toml")


def run_suite(
    suite: SuiteConfig, root: Path, order_index: int = 0, extra: Sequence[str] = ()
) -> SuiteRun:
    """Run one suite in the given order and return parsed outcomes."""
    label, order_args = order_extra(suite, order_index)
    args = list(extra) + order_args
    if suite.adapter == "pytest":
        return _pytest(suite, root, label, args)
    if suite.adapter == "junit":
        return _junit(suite, root, label, args)
    if suite.adapter in ("jest", "vitest"):
        return _jest(suite, root, label, args)
    if suite.adapter == "go":
        return _go(suite, root, label, args)
    if suite.adapter == "cargo":
        return _cargo(suite, root, label, args)
    raise ParseError(f"unknown adapter {suite.adapter}")


def isolate(suite: SuiteConfig, root: Path, test_ids: Sequence[str]) -> dict[str, str]:
    """Re-run failed IDs without the rest of the suite. Annotation only.

    Returns ``{id: "reproduces" | "passes-alone" | "unknown"}``. Supported for
    pytest (node IDs) and go (``-run``). Other adapters return "unknown".
    """
    ids = [t for t in test_ids if not t.startswith("<collect>")][: suite.isolate_max]
    if not ids:
        return {}
    if suite.adapter == "pytest":
        rerun = SuiteConfig(**{**suite.__dict__, "command": tuple(_pytest_base(suite.command))})
        try:
            result = _pytest(rerun, root, "default", ids)
        except ParseError:
            return dict.fromkeys(ids, "unknown")
        return {
            i: ("reproduces" if result.outcomes.get(i) == "failed" else "passes-alone") for i in ids
        }
    if suite.adapter == "go":
        verdicts: dict[str, str] = {}
        for test_id in ids:
            pkg, _, name = test_id.partition("::")
            if name == "<package>":
                verdicts[test_id] = "unknown"
                continue
            done = run(
                [
                    "go",
                    "test",
                    "-json",
                    "-count=1",
                    "-run",
                    f"^{re.escape(name.split('/')[0])}$",
                    pkg,
                ],
                root / suite.cwd,
                suite.timeout,
            )
            outs = parse_go_json(done.stdout)
            verdicts[test_id] = "reproduces" if outs.get(test_id) == "failed" else "passes-alone"
        return verdicts
    return dict.fromkeys(ids, "unknown")


def _pytest_base(command: Sequence[str]) -> list[str]:
    """Strip positional path arguments so explicit node IDs are the only selection."""
    out: list[str] = []
    for i, part in enumerate(command):
        if (
            i > 0
            and not part.startswith("-")
            and (Path(part).suffix == ".py" or "/" in part or part in ("tests", "test", "."))
        ):
            continue
        out.append(part)
    return out


def which(name: str) -> bool:
    return shutil.which(name) is not None
