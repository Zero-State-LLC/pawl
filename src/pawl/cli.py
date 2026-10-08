"""Command-line interface. Exit codes: 0 pass, 1 fail, 2 error (fail closed), 3 preflight."""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import json
import sys
from pathlib import Path

from pawl import __version__
from pawl.baseline import Quarantine, check_quarantine, load_baseline, write_baseline
from pawl.check import Measurement, Report, compare, in_ci, measure_all, report_path
from pawl.config import CONFIG_NAME, Config, load_config
from pawl.contract import (
    EXIT_ERROR,
    EXIT_FAIL,
    EXIT_PASS,
    EXIT_PREFLIGHT,
    SCHEMA_VERSION,
    exit_code_for,
)
from pawl.errors import PawlError, PreflightError
from pawl.guard import ESCALATIONS, GuardReport, run_guard
from pawl.render import check_markdown, guard_markdown
from pawl.trust import resolve
from pawl.update import Delta, append_debt_log, compute, default_orders

EXIT = {"pass": EXIT_PASS, "fail": EXIT_FAIL, "error": EXIT_ERROR}


def _root(args: argparse.Namespace) -> Path:
    return Path(args.root).resolve()


def _emit(text: str) -> None:
    sys.stdout.write(text if text.endswith("\n") else text + "\n")


def cmd_check(args: argparse.Namespace) -> int:
    root = _root(args)
    report = Report()
    code = 0
    try:
        gate = resolve(root, args.trusted_ref, approved=args.approved, bootstrap=args.bootstrap)
        config, notes = gate.config, list(gate.notes)
        assert gate.baseline is not None
        baseline = gate.baseline
        report.config_source = config.source
        ci = args.ci or in_ci()
        lock = args.lock if args.lock is not None else (config.lock_in_ci and ci)
        if not args.skip_preflight:
            from pawl.preflight import run_preflight

            notes += run_preflight(config)
        m = measure_all(config, ci, args.orders)
        report = compare(config, baseline, m, lock)
        report.notes = notes + report.notes
        report.approval = gate.approval.to_json() if gate.approval else None
        code = EXIT[report.status]
    except PreflightError as exc:
        report.status, report.error, code = "error", str(exc), EXIT_PREFLIGHT
    except PawlError as exc:
        report.status, report.error, code = "error", str(exc), EXIT_ERROR
    report.exit_code = code
    data = report.to_json()
    with contextlib.suppress(OSError):
        report_path(root).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    _emit(json.dumps(data, indent=2) if args.json else check_markdown(data))
    return code


def _measure_for_update(config: Config, args: argparse.Namespace) -> Measurement:
    from pawl.adapters import run_suite
    from pawl.metrics import measure

    m = Measurement()
    ci = args.ci or in_ci()
    for suite in config.suites:
        if suite.ci_only and not ci:
            continue
        count = args.orders or default_orders(suite)
        m.suites[suite.name] = [run_suite(suite, config.root, i) for i in range(count)]
    for metric in config.metrics:
        if metric.ci_only and not ci:
            continue
        m.metrics[metric.name] = measure(metric, config.root)
    return m


def _print_delta(delta: Delta) -> None:
    for item in delta.loosened:
        _emit(f"  LOOSEN   {item}")
    for item in delta.tightened:
        _emit(f"  tighten  {item}")
    for suite, ids in delta.order_dependent.items():
        _emit(f"  ORDER-DEPENDENT in {suite}: {', '.join(ids[:10])}")


def _update_json(
    status: str, code: int, delta: Delta | None = None, error: str = "", message: str = ""
) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": "pawl",
        "version": __version__,
        "kind": "update",
        "status": status,  # written | unchanged | refused | error
        "exit_code": code,
        "generated_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "error": error,
        "message": message,
        "loosened": delta.loosened if delta else [],
        "tightened": delta.tightened if delta else [],
        "order_dependent": delta.order_dependent if delta else {},
    }


def cmd_update(args: argparse.Namespace) -> int:
    root = _root(args)

    def done(status: str, code: int, delta: Delta | None, error: str = "", msg: str = "") -> int:
        if args.json:
            _emit(json.dumps(_update_json(status, code, delta, error, msg), indent=2))
        else:
            if delta is not None:
                _print_delta(delta)
            if error:
                _emit(f"error: {error}")
            if msg:
                _emit(msg)
        return code

    try:
        config = load_config(root)
        old = load_baseline(config.baseline_path) if config.baseline_path.is_file() else None
        if old is not None:
            check_quarantine(old, config.quarantine_max_days, dt.date.today(), config.baseline)
        if not args.skip_preflight:
            from pawl.preflight import run_preflight

            run_preflight(config)
        m = _measure_for_update(config, args)
        new, delta = compute(config, old, m, dt.date.today())
    except PreflightError as exc:
        return done("error", EXIT_PREFLIGHT, None, str(exc))
    except PawlError as exc:
        return done("error", EXIT_ERROR, None, str(exc))
    if delta.order_dependent and old is not None and not args.allow_order_dependent:
        return done(
            "refused",
            EXIT_FAIL,
            delta,
            msg="refused: results differ between test orders. A baseline must agree under at "
            "least two orders. Fix the order dependence, or pass --allow-order-dependent.",
        )
    if delta.loosened and not (args.loosen and args.reason):
        return done(
            "refused",
            EXIT_FAIL,
            delta,
            msg="refused: this update would loosen the baseline. A human must pass "
            '--loosen --reason "..."; the reason is written to the debt log.',
        )
    if not delta.loosened and not delta.tightened and old is not None:
        return done("unchanged", EXIT_PASS, delta, msg="baseline unchanged")
    write_baseline(config.baseline_path, new)
    append_debt_log(config.debt_log_path, "update", delta, args.reason)
    return done(
        "written", EXIT_PASS, delta, msg=f"wrote {config.baseline}; logged in {config.debt_log}"
    )


def cmd_init(args: argparse.Namespace) -> int:
    from pawl.init import detect, render_config

    root = _root(args)
    cfg_path = root / CONFIG_NAME
    if cfg_path.exists() and not args.force:
        _emit(f"error: {CONFIG_NAME} exists; use --force to overwrite")
        return 2
    try:
        adapter = args.runner or detect(root)
        cfg_path.write_text(render_config(root, adapter), encoding="utf-8")
        config = load_config(root)
        notes: list[str] = []
        if not args.skip_preflight:
            from pawl.preflight import run_preflight

            notes = run_preflight(config)
        m = _measure_for_update(config, args)
        new, delta = compute(config, None, m, dt.date.today())
    except PreflightError as exc:
        _emit(f"error: {exc}\nEdit [preflight] in {CONFIG_NAME} if the module guess is wrong.")
        return 3
    except PawlError as exc:
        _emit(f"error: {exc}")
        return 2
    write_baseline(config.baseline_path, new)
    append_debt_log(config.debt_log_path, "init", delta, "initial baseline from the current state")
    if args.github:
        from pawl.templates import GITHUB_WORKFLOW

        wf = root / ".github" / "workflows" / "pawl.yml"
        wf.parent.mkdir(parents=True, exist_ok=True)
        wf.write_text(GITHUB_WORKFLOW, encoding="utf-8")
    for n in notes:
        _emit(n)
    _print_delta(delta)
    _emit(
        f"\nWrote {CONFIG_NAME}, {config.baseline}, {config.debt_log}"
        + (", .github/workflows/pawl.yml" if args.github else "")
        + ".\nNext: commit them, make the 'pawl' CI job a required check, and add "
        f"CODEOWNERS for {CONFIG_NAME} and {config.baseline}."
    )
    return 0


def cmd_guard(args: argparse.Namespace) -> int:
    root = _root(args)
    try:
        gate = resolve(
            root, args.base, approved=args.approved, bootstrap=args.bootstrap, need_baseline=False
        )
        report = run_guard(
            gate.config,
            args.base,
            gate.approval is not None,
            args.replay,
            args.ci or in_ci(),
        )
        report.notes = gate.notes + report.notes
        report.approval = gate.approval.to_json() if gate.approval else report.approval
    except PawlError as exc:
        data = {
            "schema_version": SCHEMA_VERSION,
            "tool": "pawl",
            "version": __version__,
            "kind": "guard",
            "status": "error",
            "exit_code": EXIT_ERROR,
            "generated_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            "error": str(exc),
            "base": args.base,
            "approved": False,
            "approval": None,
            "config_source": "",
            "notes": [],
            "findings": [],
        }
        with contextlib.suppress(OSError):
            report_path(root, "last-guard.json").write_text(
                json.dumps(data, indent=2) + "\n", encoding="utf-8"
            )
        _emit(
            json.dumps(data, indent=2) if args.json else f"Pawl guard: ERROR (fail closed): {exc}"
        )
        return 2
    data = report.to_json()
    with contextlib.suppress(OSError):
        report_path(root, "last-guard.json").write_text(
            json.dumps(data, indent=2) + "\n", encoding="utf-8"
        )
    _emit(json.dumps(data, indent=2) if args.json else guard_markdown(data))
    return EXIT[report.status]


def cmd_report(args: argparse.Namespace) -> int:
    """Render the last check and guard reports.

    Exits 0 by default (it is a renderer, used to post comments), and 2 when
    there is no report to render. With --exit-status it exits with the worst
    exit code of the reports it read, so a script can gate on it: 0 only if
    every report passed.
    """
    root = _root(args)
    parts = []
    for name in ("last-report.json", "last-guard.json"):
        path = root / ".pawl" / name
        if path.is_file():
            try:
                parts.append(json.loads(path.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                parts.append({"kind": name, "status": "error", "error": "unreadable report"})
    if not parts:
        _emit("no report yet; run 'pawl check' or 'pawl guard'")
        return EXIT_ERROR
    worst = max(int(p.get("exit_code", exit_code_for(str(p.get("status"))))) for p in parts)
    status = {EXIT_PASS: "pass", EXIT_FAIL: "fail"}.get(worst, "error")
    returned = worst if args.exit_status else EXIT_PASS
    if args.format == "json":
        _emit(
            json.dumps(
                {
                    "schema_version": SCHEMA_VERSION,
                    "tool": "pawl",
                    "version": __version__,
                    "kind": "report",
                    "status": status,
                    "exit_code": returned,
                    "worst_exit_code": worst,
                    "reports": parts,
                },
                indent=2,
            )
        )
    else:
        _emit(
            "\n".join(
                check_markdown(p) if p.get("kind") == "check" else guard_markdown(p)
                for p in parts
                if p.get("kind") in ("check", "guard")
                and (p.get("status") != "error" or p.get("kind") == "check")
            )
        )
    return returned


def cmd_quarantine(args: argparse.Namespace) -> int:
    root = _root(args)
    try:
        config = load_config(root)
        baseline = load_baseline(config.baseline_path)
    except PawlError as exc:
        _emit(f"error: {exc}")
        return 2
    days = min(args.days, config.quarantine_max_days)
    expires = (dt.date.today() + dt.timedelta(days=days)).isoformat()
    baseline.quarantine.append(Quarantine(args.suite, args.test_id, args.reason, expires))
    write_baseline(config.baseline_path, baseline)
    delta = Delta(loosened=[f"quarantined {args.test_id} in {args.suite} until {expires}"])
    append_debt_log(config.debt_log_path, "quarantine", delta, args.reason)
    _emit(f"quarantined {args.test_id} until {expires} (max {config.quarantine_max_days} days)")
    return 0


def cmd_escalate(args: argparse.Namespace) -> int:
    root = _root(args)
    path = root / ESCALATIONS
    path.parent.mkdir(exist_ok=True)
    stamp = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    lines = (
        []
        if path.exists()
        else [
            "# Escalations\n\nAgents record spec or test conflicts here. A human resolves "
            "each one and changes 'open' to 'resolved'.\n"
        ]
    )
    lines.append(f"\n## {stamp} open\n")
    if args.test:
        lines.append(f"- Test: `{args.test}`")
    lines.append(f"- Why: {args.message}\n")
    with path.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    _emit(
        f"Recorded in {ESCALATIONS}. Stop work on this item and report it to the human. "
        "Do not edit the test or the baseline. The guard blocks merge until a human resolves it."
    )
    return 0


def cmd_mutate(args: argparse.Namespace) -> int:
    from pawl.mutate import run_mutation

    root = _root(args)
    try:
        mutants = run_mutation(load_config(root), args.base, args.max)
    except PawlError as exc:
        _emit(f"error: {exc}")
        return 2
    killed = sum(1 for m in mutants if m.status == "killed")
    score = killed / len(mutants) if mutants else 1.0
    code = EXIT_FAIL if args.min_score is not None and score < args.min_score else EXIT_PASS
    data = {
        "schema_version": SCHEMA_VERSION,
        "tool": "pawl",
        "version": __version__,
        "kind": "mutate",
        "status": "fail" if code else "pass",
        "exit_code": code,
        "mutants": len(mutants),
        "killed": killed,
        "score": round(score, 3),
        "survivors": [
            {"path": m.path, "line": m.line, "mutation": m.description}
            for m in mutants
            if m.status == "survived"
        ],
    }
    if args.json:
        _emit(json.dumps(data, indent=2))
    else:
        _emit(f"Mutation spot check: {killed}/{len(mutants)} killed (score {score:.2f})")
        for m in mutants:
            if m.status == "survived":
                _emit(f"  survived: {m.path}:{m.line} {m.description}")
    return code


def _hook_root(args: argparse.Namespace, payload: dict[str, object]) -> Path:
    """--root if given, else the cwd or workspace root the harness reports, else '.'."""
    if args.root != ".":
        return _root(args)
    cwd = payload.get("cwd")
    roots = payload.get("workspace_roots")
    if isinstance(cwd, str) and cwd:
        return Path(cwd).resolve()
    if isinstance(roots, list) and roots and isinstance(roots[0], str):
        return Path(roots[0]).resolve()
    return _root(args)


def _stop_budget(root: Path, payload: dict[str, object], limit: int, red: bool) -> bool:
    """Count consecutive red stops per session. Returns False once ``limit`` is spent.

    Codex has no built-in cap on Stop continuations; Claude Code and Cursor do. The
    cap keeps a gate that cannot go green from trapping the agent forever.
    """
    session = str(payload.get("session_id") or payload.get("conversation_id") or "default")
    path = root / ".pawl" / "hook-state.json"
    try:
        state = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, ValueError):
        state = {}
    if not isinstance(state, dict):
        state = {}
    count = int(state.get(session, 0)) + 1 if red else 0
    state[session] = count
    with contextlib.suppress(OSError):
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(state), encoding="utf-8")
    return count <= limit


def cmd_hook(args: argparse.Namespace) -> int:
    from pawl.hooks import protect_decision, protect_output, read_stdin_json, stop_output

    payload = read_stdin_json()
    root = _hook_root(args, payload)
    if args.event == "protect":
        try:
            config = load_config(root)
        except PawlError:
            return 0
        block = protect_decision(config, payload)
        if block is None:
            return 0
        out, err, code = protect_output(args.format, block)
        if out:
            _emit(out)
        if err:
            sys.stderr.write(err + "\n")
        return code
    reason: str | None = None
    try:
        # With --base, the same trust model as CI: the gate definition comes from the base ref.
        gate = resolve(root, args.base)
        config = gate.config
        assert gate.baseline is not None
        baseline = gate.baseline
        from pawl.preflight import run_preflight

        run_preflight(config)
        report = compare(config, baseline, measure_all(config, ci=False), lock=False)
        report_path(root).write_text(
            json.dumps(report.to_json(), indent=2) + "\n", encoding="utf-8"
        )
        lines = [
            f"{p.code} {p.subject}: {p.message} {', '.join(p.ids[:5])}" for p in report.problems
        ]
        if args.base:
            g: GuardReport = run_guard(config, args.base, replay=True)
            lines += [
                f"{f.rule} {f.path}: {f.message}" for f in g.findings if f.severity == "block"
            ]
        if lines:
            steps = report.to_json()["next_steps"]
            reason = (
                "Pawl gate is red. You are not done.\n" + "\n".join(lines) + "\n" + "\n".join(steps)
            )
    except PawlError as exc:
        reason = f"Pawl could not verify the work (fail closed): {exc}"
    if not _stop_budget(root, payload, args.max_blocks, reason is not None):
        sys.stderr.write(
            f"Pawl: gate still red after {args.max_blocks} attempts; allowing the stop. "
            "Report the red gate to the human; do not claim the work is done.\n"
        )
        reason = None
    _emit(stop_output(args.format, reason))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pawl",
        description="Ratchet gate for automated coding work. Code can only move forward.",
    )
    p.add_argument("--version", action="version", version=f"pawl {__version__}")
    p.add_argument("--root", default=".", help="project root (default: current directory)")
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("check", help="run the gate; exit 0 only if nothing regressed")
    c.add_argument("--json", action="store_true", help="print the JSON report")
    c.add_argument("--trusted-ref", help="load the gate definition from this base ref (use in CI)")
    c.add_argument(
        "--approved", action="store_true", help="human-approved change: use the head config"
    )
    c.add_argument(
        "--ci", action="store_true", help="treat as CI (run ci_only suites, lock baseline)"
    )
    c.add_argument(
        "--lock",
        dest="lock",
        action="store_true",
        default=None,
        help="fail if the baseline is looser than reality",
    )
    c.add_argument("--no-lock", dest="lock", action="store_false")
    c.add_argument("--orders", type=int, help="run each suite in N orders (default: check_orders)")
    c.add_argument("--skip-preflight", action="store_true")
    c.add_argument(
        "--bootstrap",
        action="store_true",
        help="allow a trusted ref with no pawl.toml (the change that adds Pawl)",
    )
    c.set_defaults(func=cmd_check)

    u = sub.add_parser("update", help="record the current state; only tightening unless --loosen")
    u.add_argument("--loosen", action="store_true", help="allow loosening (humans only)")
    u.add_argument("--reason", help="why; required with --loosen, written to the debt log")
    u.add_argument("--orders", type=int, help="confirm under N orders (default 2 where supported)")
    u.add_argument("--allow-order-dependent", action="store_true")
    u.add_argument("--ci", action="store_true", help="include ci_only suites")
    u.add_argument("--skip-preflight", action="store_true")
    u.add_argument("--json", action="store_true", help="print the result as JSON")
    u.set_defaults(func=cmd_update)

    i = sub.add_parser("init", help="detect the runner, write pawl.toml and the first baseline")
    i.add_argument("--runner", choices=["pytest", "jest", "vitest", "go", "cargo"])
    i.add_argument("--force", action="store_true")
    i.add_argument("--github", action="store_true", help="also write .github/workflows/pawl.yml")
    i.add_argument("--orders", type=int)
    i.add_argument("--ci", action="store_true")
    i.add_argument("--skip-preflight", action="store_true")
    i.set_defaults(func=cmd_init)

    g = sub.add_parser("guard", help="flag tampering in the diff against a base ref")
    g.add_argument("--base", required=True, help="base ref, for example origin/main")
    g.add_argument("--replay", action="store_true", help="run the base versions of changed tests")
    g.add_argument("--approved", action="store_true", help="a human approved this change")
    g.add_argument("--json", action="store_true")
    g.add_argument("--ci", action="store_true")
    g.add_argument(
        "--bootstrap",
        action="store_true",
        help="allow a base ref with no pawl.toml (the change that adds Pawl)",
    )
    g.set_defaults(func=cmd_guard)

    r = sub.add_parser("report", help="render the last check and guard reports")
    r.add_argument("--format", choices=["md", "json"], default="md")
    r.add_argument(
        "--exit-status",
        action="store_true",
        help="exit with the worst exit code of the reports (default: always 0)",
    )
    r.set_defaults(func=cmd_report)

    q = sub.add_parser("quarantine", help="excuse a flaky test until an expiry date (humans only)")
    q.add_argument("test_id")
    q.add_argument("--suite", required=True)
    q.add_argument("--reason", required=True)
    q.add_argument("--days", type=int, default=14)
    q.set_defaults(func=cmd_quarantine)

    e = sub.add_parser("escalate", help="record a spec or test conflict for a human, then stop")
    e.add_argument("message")
    e.add_argument("--test", help="the test ID involved")
    e.set_defaults(func=cmd_escalate)

    mu = sub.add_parser("mutate", help="advisory mutation spot check on changed Python lines")
    mu.add_argument("--base", required=True)
    mu.add_argument("--max", type=int, default=10)
    mu.add_argument("--min-score", type=float)
    mu.add_argument("--json", action="store_true")
    mu.set_defaults(func=cmd_mutate)

    h = sub.add_parser(
        "hook", help="harness hooks: 'stop' (done check) and 'protect' (block gate edits)"
    )
    h.add_argument("event", choices=["stop", "protect"])
    h.add_argument("--format", choices=["claude", "codex", "hermes", "cursor"], default="claude")
    h.add_argument("--base", help="also run the guard against this ref (stop only)")
    h.add_argument(
        "--max-blocks",
        type=int,
        default=5,
        help="stop only: consecutive red stops before giving up",
    )
    h.set_defaults(func=cmd_hook)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    code: int = args.func(args)
    return code
