"""Tamper guard: diff against the base branch and flag changes that weaken the gate.

Evidence behind each rule is in RESEARCH.md. In short: agents edit or delete
tests, add skips, overload equality, sniff the test environment, and patch the
evaluator (ImpossibleBench https://arxiv.org/abs/2510.20270, METR 2025
https://metr.org/blog/2025-06-05-recent-reward-hacking/). Test-file edit
detection is a reliable signal (EvilGenie https://arxiv.org/abs/2511.21654),
and replaying the original tests catches edits that weaken them (Baker et al.
https://arxiv.org/abs/2503.11926).
"""

from __future__ import annotations

import ast
import configparser
import datetime as dt
import json
import re
import shutil
import tempfile
import tomllib
from dataclasses import dataclass, field, replace
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

from pawl import __version__
from pawl.baseline import Quarantine, parse_baseline
from pawl.config import Config
from pawl.contract import SCHEMA_VERSION, exit_code_for
from pawl.errors import PawlError
from pawl.gitutil import changed_files, diff_text, git, merge_base, prefix, show, toplevel

ESCALATIONS = ".pawl/ESCALATIONS.md"

SKIP_MARKERS = [
    (r"@pytest\.mark\.(skip|skipif|xfail)\b", "pytest skip/xfail marker"),
    (r"\bpytest\.(skip|xfail|importorskip)\(", "pytest runtime skip"),
    (r"\bpytestmark\s*=", "module-level pytest marker"),
    (r"@unittest\.(skip|skipIf|skipUnless|expectedFailure)\b", "unittest skip"),
    (r"\.skipTest\(", "unittest skipTest"),
    (r"\b(it|test|describe)\.(skip|only|todo|failing)\(", "JS skip/only"),
    (r"\b(xit|xdescribe|xtest|fit|fdescribe)\(", "JS skip/focus"),
    (r"\bt\.Skip(Now|f)?\(", "Go t.Skip"),
    (r"#\[ignore\b", "Rust #[ignore]"),
]

HOOK_PATTERNS = [
    (
        r"def pytest_(runtest_makereport|runtest_call|runtest_protocol|pyfunc_call"
        r"|collection_modifyitems|report_teststatus|terminal_summary|assertrepr_compare)\b",
        "pytest hook that can rewrite outcomes",
    ),
    (r"\bpytest_plugins\s*=", "pytest plugin injection"),
]

SUSPICIOUS_BLOCK = [
    (r"PYTEST_CURRENT_TEST", "code detects that it runs under pytest"),
    (
        r"""["']pytest["']\s+in\s+sys\.modules|sys\.modules\[\s*["']_?pytest""",
        "code detects that it runs under pytest",
    ),
    (r"JEST_WORKER_ID|process\.env\.VITEST\b", "code detects that it runs under a JS test runner"),
    (r"\btesting\.Testing\(\)", "Go code detects that it runs under go test"),
    (
        r"def __eq__\([^)]*\)[^:\n]*:\s*(#[^\n]*)?\n?\s*return True\b",
        "__eq__ that always returns True",
    ),
    (r"__eq__\s*=\s*lambda[^:\n]*:\s*True\b", "__eq__ that always returns True"),
]

SUSPICIOUS_WARN = [
    (
        r"\binspect\.stack\(|\bsys\._getframe\(|traceback\.extract_stack\(",
        "inspects the call stack",
    ),
    (r"^\s*(import pytest|from _?pytest)", "imports pytest from non-test code"),
    (r"\bunittest\.mock\.patch\b|\bmonkeypatch\b", "patching in non-test code"),
]


@dataclass
class Finding:
    """One guard finding."""

    rule: str
    severity: str  # block | warn | info | approved
    path: str
    message: str
    ids: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "path": self.path,
            "message": self.message,
            "ids": self.ids[:25],
        }


@dataclass
class GuardReport:
    """Guard verdict."""

    base: str
    findings: list[Finding] = field(default_factory=list)
    approved: bool = False
    config_source: str = ""
    notes: list[str] = field(default_factory=list)
    approval: dict[str, Any] | None = None

    @property
    def status(self) -> str:
        return "fail" if any(f.severity == "block" for f in self.findings) else "pass"

    def to_json(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "tool": "pawl",
            "version": __version__,
            "kind": "guard",
            "status": self.status,
            "exit_code": exit_code_for(self.status),
            "generated_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            "base": self.base,
            "approved": self.approved,
            "approval": self.approval,
            "config_source": self.config_source,
            "notes": self.notes,
            "findings": [f.to_json() for f in self.findings],
        }


def glob_match(path: str, pattern: str) -> bool:
    if fnmatchcase(path, pattern):
        return True
    return pattern.startswith("**/") and fnmatchcase(path, pattern[3:])


def matches_any(path: str, patterns: tuple[str, ...] | list[str]) -> bool:
    return any(glob_match(path, p) for p in patterns)


def root_relative(path: str, pre: str) -> str | None:
    """A top-level-relative git path made relative to the Pawl root, or None if outside it."""
    if not pre:
        return path
    return path[len(pre) :] if path.startswith(pre) else None


def _matches(path: str, rel: str | None, patterns: tuple[str, ...] | list[str]) -> bool:
    """Match a changed file by its root-relative path and by its top-level path.

    Top-level matching keeps repository-wide gate files (``.github/workflows/**``)
    protected when the Pawl root is a subdirectory.
    """
    return (rel is not None and matches_any(rel, patterns)) or matches_any(path, patterns)


def split_diff(diff: str) -> tuple[list[str], list[str]]:
    """Return (removed, added) content lines from a unified diff."""
    removed: list[str] = []
    added: list[str] = []
    for line in diff.splitlines():
        if line.startswith(("---", "+++", "@@", "diff ", "index ")):
            continue
        if line.startswith("-"):
            removed.append(line[1:])
        elif line.startswith("+"):
            added.append(line[1:])
    return removed, added


def _meaningful(lines: list[str]) -> list[str]:
    return [line for line in lines if line.strip() and not line.strip().startswith(("#", "//"))]


def _scan(lines: list[str], patterns: list[tuple[str, str]]) -> list[str]:
    text = "\n".join(lines)
    hits = []
    for pattern, label in patterns:
        if re.search(pattern, text, flags=re.MULTILINE):
            hits.append(label)
    return hits


def shadowed_tests(source: str) -> list[str]:
    """Python test functions defined twice in one scope; the later one silently wins."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    dupes: list[str] = []

    def visit(body: list[ast.stmt], scope: str) -> None:
        seen: set[str] = set()
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
                "test"
            ):
                if node.name in seen:
                    dupes.append(f"{scope}{node.name}")
                seen.add(node.name)
            elif isinstance(node, ast.ClassDef):
                if node.name in seen:
                    dupes.append(f"{scope}{node.name}")
                seen.add(node.name)
                visit(node.body, f"{scope}{node.name}.")

    visit(tree.body, "")
    return dupes


def baseline_changes(base_text: str | None, head_text: str | None) -> tuple[list[str], list[str]]:
    """Classify a baseline file change into (loosened, tightened) descriptions.

    Default deny: every field Pawl reads is compared, and any change that is not
    a recognized tightening is reported as loosened.
    """
    if head_text is None:
        return ["baseline file deleted"], []
    if base_text is None:
        return [], ["baseline file added"]
    try:
        old = parse_baseline(base_text, "base baseline")
        new = parse_baseline(head_text, "head baseline")
    except PawlError as exc:
        return [f"baseline unreadable: {exc}"], []
    loosened: list[str] = []
    tightened: list[str] = []
    for name, prev in old.suites.items():
        cur = new.suites.get(name)
        if cur is None:
            loosened.append(f"{name}: suite removed from baseline")
            continue
        if set(cur.failing_ids) - set(prev.failing_ids):
            loosened.append(f"{name}: failing IDs added")
        if set(prev.failing_ids) - set(cur.failing_ids):
            tightened.append(f"{name}: failing IDs removed")
        if cur.collected < prev.collected:
            loosened.append(f"{name}: collected floor lowered {prev.collected} -> {cur.collected}")
        if set(prev.collected_ids) - set(cur.collected_ids):
            loosened.append(f"{name}: collected IDs removed")
        if (set(cur.skipped_ids) & set(prev.collected_ids)) - set(prev.skipped_ids):
            loosened.append(f"{name}: skipped IDs added")
        if prev.identity == "ids" and cur.identity != "ids":
            loosened.append(f"{name}: identity weakened to count")
        if set(cur.order_dependent) - set(prev.order_dependent):
            loosened.append(f"{name}: order-dependent IDs added")
        if cur.confirmed_orders < prev.confirmed_orders:
            loosened.append(
                f"{name}: confirmed_orders lowered {prev.confirmed_orders} -> "
                f"{cur.confirmed_orders}"
            )
    for name in sorted(set(new.suites) - set(old.suites)):
        tightened.append(f"{name}: suite added")
    for name, pm in old.metrics.items():
        cm = new.metrics.get(name)
        if cm is None:
            loosened.append(f"{name}: metric removed from baseline")
            continue
        before, after = float(pm["value"]), float(cm["value"])
        if cm.get("direction") != pm.get("direction"):
            loosened.append(f"{name}: direction changed")
        elif (after > before) if pm["direction"] == "down" else (after < before):
            loosened.append(f"{name}: {before:g} -> {after:g}")
        elif after != before:
            tightened.append(f"{name}: {before:g} -> {after:g}")
        extra_old = {k: v for k, v in pm.items() if k not in ("value", "direction")}
        extra_new = {k: v for k, v in cm.items() if k not in ("value", "direction")}
        if extra_old != extra_new:
            loosened.append(f"{name}: unrecognized metric fields changed")
    for name in sorted(set(new.metrics) - set(old.metrics)):
        tightened.append(f"{name}: metric added")

    # Quarantine entries are compared whole: a longer expiry or a new reason is
    # a new excuse, not the old one (review finding F3).
    def entry(q: Quarantine) -> tuple[str, str, str, str]:
        return (q.suite, q.test_id, q.reason, q.expires)

    old_q = {entry(q) for q in old.quarantine}
    new_q = {entry(q) for q in new.quarantine}
    old_by_key = {(q.suite, q.test_id): q for q in old.quarantine}
    for suite, test_id, reason, expires in sorted(new_q - old_q):
        prev_q = old_by_key.get((suite, test_id))
        if prev_q is not None and prev_q.reason == reason and expires < prev_q.expires:
            tightened.append(f"quarantine shortened: {test_id} until {expires}")
            continue
        verb = "changed" if prev_q is not None else "added"
        loosened.append(f"quarantine {verb}: {test_id} until {expires} ({reason})")
    new_keys = {(q.suite, q.test_id) for q in new.quarantine}
    for _suite, test_id, _reason, _expires in sorted(old_q - new_q):
        if (_suite, test_id) not in new_keys:
            tightened.append(f"quarantine removed: {test_id}")
    return loosened, tightened


def _test_config_view(path: str, text: str | None) -> Any:
    """Extract only the test-runner settings of a shared config file."""
    if text is None:
        return None
    name = Path(path).name
    try:
        if name == "pyproject.toml":
            tool = tomllib.loads(text).get("tool", {})
            return {k: tool.get(k) for k in ("pytest", "coverage", "pawl")}
        if name == "setup.cfg":
            cp = configparser.ConfigParser(interpolation=None)
            cp.read_string(text)
            return {
                s: dict(cp[s])
                for s in cp.sections()
                if s in ("tool:pytest",) or s.startswith("coverage:")
            }
        if name == "package.json":
            data = json.loads(text)
            return {
                "jest": data.get("jest"),
                "vitest": data.get("vitest"),
                "test": (data.get("scripts") or {}).get("test"),
            }
        if name == "Cargo.toml":
            data = tomllib.loads(text)
            return {k: data.get(k) for k in ("test", "lib", "bin")}
    except (tomllib.TOMLDecodeError, configparser.Error, json.JSONDecodeError):
        return {"unparseable": True}
    return None


SHARED_CONFIGS = ("pyproject.toml", "setup.cfg", "package.json", "Cargo.toml")


def run_guard(
    config: Config,
    base: str,
    approved: bool = False,
    replay: bool = False,
    ci: bool = False,
) -> GuardReport:
    """Diff the working tree against ``base`` and report tampering.

    Git reports paths from the repository top level. When the Pawl root is a
    subdirectory, each path is also matched relative to the root, so
    ``pkg/pawl.toml`` is the gate config of a root at ``pkg/``.
    """
    root = config.root
    top = toplevel(root)
    pre = prefix(root)
    mb = merge_base(root, base)
    report = GuardReport(base=f"{base} ({mb[:12]})", approved=approved, config_source=config.source)
    if pre:
        report.notes.append(f"root is {pre.rstrip('/')}/ inside the repository")
    test_changes: list[str] = []
    for status, path in changed_files(top, mb):
        rel = root_relative(path, pre)
        head_file = top / path
        head_text = (
            head_file.read_text(encoding="utf-8", errors="replace") if head_file.is_file() else None
        )
        base_text = show(top, mb, path) if status != "A" else None
        removed, added = (
            split_diff(diff_text(top, mb, path))
            if status != "A"
            else ([], (head_text or "").splitlines())
        )
        if rel == config.baseline:
            loosened, tightened = baseline_changes(base_text, head_text)
            for item in loosened:
                report.findings.append(Finding("BASELINE_LOOSENED", "block", path, item))
            for item in tightened:
                report.findings.append(Finding("BASELINE_TIGHTENED", "info", path, item))
            # The baseline is a gate file: every edit is on the record. Only a
            # change that is entirely a recognized tightening (the output of an
            # honest 'pawl update') is informational; anything else blocks.
            report.findings.append(
                Finding(
                    "PROTECTED_CHANGED",
                    "block" if loosened else "info",
                    path,
                    "baseline changed: "
                    + ("loosened or unrecognized change" if loosened else "tightening only"),
                )
            )
            continue
        if rel == config.debt_log:
            if _meaningful(removed):
                report.findings.append(
                    Finding("DEBT_LOG_REWRITTEN", "block", path, "the debt log is append-only")
                )
            else:
                report.findings.append(
                    Finding("DEBT_LOG_CHANGED", "info", path, "debt log updated")
                )
            continue
        if rel == ESCALATIONS:
            opened = [line for line in added if re.match(r"^## .*\bopen\s*$", line)]
            closed = [line for line in removed if re.match(r"^## .*\bopen\s*$", line)]
            if closed:
                report.findings.append(
                    Finding(
                        "ESCALATION_RESOLVED",
                        "block",
                        path,
                        f"{len(closed)} escalation(s) closed in this change; a human must approve",
                    )
                )
            if opened:
                report.findings.append(
                    Finding(
                        "ESCALATION_OPEN",
                        "block",
                        path,
                        f"{len(opened)} open escalation(s): a human must decide",
                    )
                )
            continue
        if _matches(path, rel, config.guard.protected):
            verb = {"A": "added", "M": "modified", "D": "deleted"}.get(status, status)
            report.findings.append(
                Finding("PROTECTED_CHANGED", "block", path, f"protected gate file {verb}")
            )
        is_test = _matches(path, rel, config.guard.tests)
        if is_test:
            if status == "D":
                report.findings.append(Finding("TEST_DELETED", "block", path, "test file deleted"))
                test_changes.append(path)
                continue
            gone = _meaningful(removed)
            if gone:
                report.findings.append(
                    Finding(
                        "TEST_MODIFIED",
                        "block",
                        path,
                        f"{len(gone)} existing test line(s) changed or removed; "
                        "existing tests are read-only for agents",
                    )
                )
                test_changes.append(path)
            for label in _scan(added, SKIP_MARKERS):
                report.findings.append(Finding("SKIP_ADDED", "block", path, f"added {label}"))
            if path.endswith(".py") and head_text:
                for name in shadowed_tests(head_text):
                    report.findings.append(
                        Finding(
                            "TEST_SHADOWED",
                            "block",
                            path,
                            f"{name} is defined twice; the first is never run",
                        )
                    )
        if path.endswith(".py"):
            for label in _scan(added, HOOK_PATTERNS):
                report.findings.append(Finding("HOOK_TAMPER", "block", path, f"added {label}"))
        if (
            Path(path).name in SHARED_CONFIGS
            and status == "M"
            and _test_config_view(path, base_text) != _test_config_view(path, head_text)
        ):
            report.findings.append(
                Finding(
                    "TEST_CONFIG_CHANGED",
                    "block",
                    path,
                    "test runner or coverage settings changed",
                )
            )
        if not is_test and status != "D":
            for label in _scan(added, SUSPICIOUS_BLOCK):
                report.findings.append(Finding("SUSPICIOUS_CODE", "block", path, label))
            sev = "block" if config.guard.fail_on_suspicious else "warn"
            for label in _scan(added, SUSPICIOUS_WARN):
                report.findings.append(Finding("SUSPICIOUS_CODE", sev, path, label))
    if replay and test_changes:
        report.findings += replay_base_tests(config, mb, test_changes, ci)
    if approved:
        for f in report.findings:
            if f.severity == "block":
                f.severity = "approved"
    return report


def replay_base_tests(config: Config, mb: str, paths: list[str], ci: bool) -> list[Finding]:
    """Run the base branch's versions of changed tests against the current code.

    If the original tests fail where the edited tests pass, the edit weakened
    the tests. This is how Baker et al. labeled cheating in agentic coding
    environments (https://arxiv.org/abs/2503.11926).
    """
    from pawl.check import compare, measure_all

    top = toplevel(config.root)
    pre = prefix(config.root)
    base_baseline_text = show(top, mb, pre + config.baseline)
    if base_baseline_text is None:
        return [Finding("REPLAY_SKIPPED", "warn", "", "no baseline on the base branch")]
    tmp = Path(tempfile.mkdtemp(prefix="pawl-replay-"))
    wt = tmp / "wt"
    git(top, "worktree", "add", "--detach", str(wt), "HEAD")
    try:
        for status, path in changed_files(top, "HEAD"):
            dst = wt / path
            if status == "D":
                dst.unlink(missing_ok=True)
            elif (top / path).is_file():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(top / path, dst)
        for path in paths:
            content = show(top, mb, path)
            if content is None:
                continue
            (wt / path).parent.mkdir(parents=True, exist_ok=True)
            (wt / path).write_text(content, encoding="utf-8")
        cfg = replace(config, root=wt / pre if pre else wt, metrics=())
        m = measure_all(cfg, ci=ci, orders=1)
        result = compare(cfg, parse_baseline(base_baseline_text), m, lock=False)
    finally:
        git(top, "worktree", "remove", "--force", str(wt), check=False)
        shutil.rmtree(tmp, ignore_errors=True)
    findings = []
    for p in result.problems:
        if p.code in ("NEW_FAILURE", "MISSING_TESTS", "NEWLY_SKIPPED", "COLLECTION_DROP"):
            findings.append(
                Finding(
                    "TESTS_WEAKENED_REPLAY",
                    "block",
                    ", ".join(paths[:5]),
                    f"the original tests fail on this code ({p.code}: {p.message})",
                    p.ids,
                )
            )
    if not findings:
        findings.append(
            Finding(
                "REPLAY_PASSED",
                "info",
                ", ".join(paths[:5]),
                "original tests still pass on this code",
            )
        )
    return findings
