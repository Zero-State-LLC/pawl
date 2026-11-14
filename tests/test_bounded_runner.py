from __future__ import annotations

import json
import os
import signal
import sys
import time
from pathlib import Path

import pytest
from tests.conftest import commit, edit, git

from pawl import runner
from pawl.adapters import run_suite
from pawl.cli import main
from pawl.config import load_config, parse_config
from pawl.errors import ConfigError, PawlError
from pawl.guard import run_guard
from pawl.metrics import measure
from pawl.preflight import run_preflight
from pawl.runner import ExecutionError, ExecutionLimits, run

LIMITS = ExecutionLimits(65536, 0.05)


def execute(root: Path, code: str, timeout: float = 2.0) -> runner.Completed:
    return run([sys.executable, "-c", code], root, timeout, limits=LIMITS)


def alive(pid: int) -> bool:
    state = Path(f"/proc/{pid}/stat")
    if state.exists() and state.read_text().split()[2] == "Z":
        return False  # Non-child zombies are the host reaper's responsibility.
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def assert_stopped(pid: int) -> None:
    deadline = time.monotonic() + 2
    while alive(pid) and time.monotonic() < deadline:
        time.sleep(0.01)
    assert not alive(pid)


def test_exact_combined_byte_budget_passes(tmp_path: Path) -> None:
    result = execute(tmp_path, "import os; os.write(1,b'a'*32768); os.write(2,b'b'*32768)")
    assert result.returncode == 0
    assert result.stdout == "a" * 32768 and result.stderr == "b" * 32768


@pytest.mark.parametrize("stream", [1, 2])
def test_flood_terminates_without_partial_success(tmp_path: Path, stream: int) -> None:
    with pytest.raises(ExecutionError) as error:
        execute(tmp_path, f"import os\nwhile True: os.write({stream},b'x'*8192)")
    assert error.value.code == "OUTPUT_LIMIT"
    assert "xxxx" not in str(error.value)


def test_budget_counts_bytes_before_utf8_decoding(tmp_path: Path) -> None:
    result = execute(tmp_path, "import os; os.write(1,b'\\xff'*65536)")
    assert len(result.stdout) == 65536
    with pytest.raises(ExecutionError, match="OUTPUT_LIMIT"):
        execute(tmp_path, "import os; os.write(1,b'\\xff'*65537)")


def test_large_single_line_diagnostic_is_bounded(tmp_path: Path) -> None:
    result = execute(tmp_path, "print('x'*50000)")
    assert len(result.tail()) < 4200


def test_timeout_reaps_direct_child(tmp_path: Path) -> None:
    code = "import os,time; open('pid','w').write(str(os.getpid())); time.sleep(60)"
    started = time.monotonic()
    with pytest.raises(ExecutionError) as error:
        execute(tmp_path, code, 0.3)
    assert error.value.code == "RUN_TIMEOUT"
    assert time.monotonic() - started < 3
    pid = int((tmp_path / "pid").read_text())
    assert_stopped(pid)
    with pytest.raises(ChildProcessError):
        os.waitpid(pid, os.WNOHANG)


def test_grandchild_holding_pipes_cannot_extend_deadline(tmp_path: Path) -> None:
    grandchild = "import os,signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); open('grandchild','w').write(str(os.getpid())); time.sleep(60)"
    parent = f"import subprocess,sys; subprocess.Popen([sys.executable,'-c',{grandchild!r}])"
    started = time.monotonic()
    try:
        with pytest.raises(ExecutionError, match="RUN_TIMEOUT"):
            execute(tmp_path, parent, 0.5)
        assert time.monotonic() - started < 3
        assert_stopped(int((tmp_path / "grandchild").read_text()))
    finally:
        path = tmp_path / "grandchild"
        if path.exists() and alive(int(path.read_text())):
            os.kill(int(path.read_text()), signal.SIGKILL)


def test_closed_pipes_do_not_hide_running_child(tmp_path: Path) -> None:
    with pytest.raises(ExecutionError, match="RUN_TIMEOUT"):
        execute(tmp_path, "import os,time; os.close(1); os.close(2); time.sleep(60)", 0.2)


def test_interrupt_cleans_up_and_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    processes = []
    popen = runner.subprocess.Popen

    def capture(*args, **kwargs):
        process = popen(*args, **kwargs)
        processes.append(process)
        return process

    class InterruptingSelector(runner.selectors.DefaultSelector):
        def select(self, timeout=None):
            raise KeyboardInterrupt

    monkeypatch.setattr(runner.subprocess, "Popen", capture)
    monkeypatch.setattr(runner.selectors, "DefaultSelector", InterruptingSelector)
    with pytest.raises(ExecutionError, match="RUN_INTERRUPTED"):
        execute(tmp_path, "import time; time.sleep(60)")
    assert len(processes) == 1 and processes[0].poll() is not None
    with pytest.raises(ChildProcessError):
        os.waitpid(processes[0].pid, os.WNOHANG)


def test_failed_group_signal_never_reports_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def deny(pid: int, sig: int) -> None:
        raise PermissionError("synthetic denied signal")

    monkeypatch.setattr(runner.os, "killpg", deny)
    with pytest.raises(ExecutionError, match="TERMINATION_UNCERTAIN"):
        execute(tmp_path, "pass")


def test_unsupported_platform_fails_before_spawn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner, "POSIX", False)
    with pytest.raises(ExecutionError, match="UNSUPPORTED_PLATFORM"):
        execute(tmp_path, "open('must-not-exist','w').write('bad')")
    assert not (tmp_path / "must-not-exist").exists()


def config(root: Path, execution: str = "max_output_bytes = 65536\nterminate_grace_seconds = 0.05"):
    return parse_config(
        """[execution]
"""
        + execution
        + """
[[suite]]
name = "tests"
adapter = "junit"
command = ["python", "probe.py"]
junit_path = "report.xml"
[[metric]]
name = "count"
command = ["python", "probe.py"]
direction = "down"
extract = "count-regex:bad"
[preflight]
commands = [["python", "probe.py"]]
""",
        root,
    )


@pytest.mark.parametrize(
    "source",
    [
        "max_output_bytes = true",
        "max_output_bytes = 65535",
        "max_output_bytes = 67108865",
        'max_output_bytes = "65536"',
        "terminate_grace_seconds = nan",
        "terminate_grace_seconds = inf",
        "terminate_grace_seconds = -1",
        "terminate_grace_seconds = 31",
        "terminate_grace_seconds = false",
    ],
)
def test_invalid_execution_policy_rejected(tmp_path: Path, source: str) -> None:
    with pytest.raises(ConfigError):
        config(tmp_path, source)


@pytest.mark.parametrize(
    "value", ["true", "0", "-1", "nan", "inf", '"5"', pytest.param("9" * 400, id="too-large")]
)
def test_invalid_suite_timeout_rejected(tmp_path: Path, value: str) -> None:
    with pytest.raises(ConfigError):
        parse_config(
            f'[[suite]]\nname="a"\nadapter="pytest"\ncommand=["pytest"]\ntimeout={value}\n',
            tmp_path,
        )


@pytest.mark.parametrize("caller", ["suite", "metric", "preflight"])
def test_limits_apply_to_all_measurement_paths(tmp_path: Path, caller: str) -> None:
    (tmp_path / "probe.py").write_text(
        "import os\nopen('report.xml','w').write('<testsuite><testcase name=\"ok\"/></testsuite>')\nos.write(1,b'x'*65537)\n"
    )
    cfg = config(tmp_path)
    with pytest.raises(ExecutionError, match="OUTPUT_LIMIT"):
        if caller == "suite":
            run_suite(cfg.suites[0], tmp_path)
        elif caller == "metric":
            measure(cfg.metrics[0], tmp_path)
        else:
            run_preflight(cfg)


def test_cli_check_exposes_typed_resource_error(tmp_path: Path) -> None:
    (tmp_path / "pawl.toml").write_text("""[execution]
max_output_bytes = 65536
[[metric]]
name = "count"
command = ["python", "probe.py"]
direction = "down"
extract = "count-regex:bad"
""")
    (tmp_path / "pawl.baseline.json").write_text(
        json.dumps(
            {
                "pawl_baseline": 1,
                "suites": {},
                "metrics": {"count": {"value": 0, "direction": "down"}},
            }
        )
    )
    (tmp_path / "probe.py").write_text("import os; os.write(1,b'x'*65537)")
    assert main(["--root", str(tmp_path), "check", "--json"]) == 2
    report = json.loads((tmp_path / ".pawl/last-report.json").read_text())
    assert report["error_code"] == "OUTPUT_LIMIT" and report["status"] == "error"


def test_replay_timeout_removes_worktree(demo_repo: Path) -> None:
    cfg = demo_repo / "pawl.toml"
    cfg.write_text(cfg.read_text().replace('name = "tests"', 'name = "tests"\ntimeout = 0.3'))
    commit(demo_repo, "trusted short timeout")
    git(demo_repo, "branch", "-f", "main", "HEAD")
    edit(
        demo_repo / "calc/__init__.py",
        "return a - b",
        "import time; time.sleep(60)\n    return a - b",
    )
    edit(
        demo_repo / "tests/test_calc.py", "def test_subtract():", "def test_subtract():\n    return"
    )
    before = git(demo_repo, "worktree", "list", "--porcelain")
    with pytest.raises(ExecutionError, match="RUN_TIMEOUT"):
        run_guard(load_config(demo_repo), "main", replay=True)
    assert git(demo_repo, "worktree", "list", "--porcelain") == before


def test_replay_cleanup_failure_is_not_pass(
    demo_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pawl import guard as guard_module

    original = guard_module.git

    def fail_remove(root, *args, **kwargs):
        if args[:2] == ("worktree", "remove"):
            raise PawlError("simulated cleanup failure")
        return original(root, *args, **kwargs)

    edit(demo_repo / "tests/test_calc.py", "def test_add():", "# harmless comment\ndef test_add():")
    monkeypatch.setattr(guard_module, "git", fail_remove)
    try:
        with pytest.raises(ExecutionError, match="TERMINATION_UNCERTAIN"):
            run_guard(load_config(demo_repo), "main", replay=True)
    finally:
        git(demo_repo, "worktree", "prune")


def test_unapproved_head_cannot_raise_output_cap(demo_repo: Path) -> None:
    cfg = demo_repo / "pawl.toml"
    cfg.write_text(cfg.read_text() + "\n[execution]\nmax_output_bytes = 65536\n")
    commit(demo_repo, "trusted output limit")
    git(demo_repo, "branch", "-f", "main", "HEAD")
    edit(cfg, "max_output_bytes = 65536", "max_output_bytes = 131072")
    (demo_repo / "tools/todo_lint.py").write_text("import os; os.write(1,b'x'*65537)")
    assert main(["--root", str(demo_repo), "check", "--ci", "--trusted-ref", "main", "--json"]) == 2
    report = json.loads((demo_repo / ".pawl/last-report.json").read_text())
    assert report["error_code"] == "OUTPUT_LIMIT"
