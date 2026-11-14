"""Environment policy, caller propagation, cleanup, and secret-free policy reporting."""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from benchmarks.corpus import ENVIRONMENT_SCENARIOS

from pawl.adapters import run_suite
from pawl.cli import main
from pawl.config import SuiteConfig, parse_config
from pawl.environment import EnvironmentPolicyError, command_environment
from pawl.errors import ConfigError
from pawl.preflight import run_preflight
from pawl.runner import ExecutionError, ExecutionLimits, run

MINIMAL = ExecutionLimits(environment="minimal")
SECRET = "synthetic-marker-not-a-real-credential"


@pytest.mark.parametrize("case", ENVIRONMENT_SCENARIOS, ids=[c[0] for c in ENVIRONMENT_SCENARIOS])
def test_cli_environment_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    case: tuple[str, str, list[str], int],
) -> None:
    _, mode, allowed, code = case
    monkeypatch.setenv("PAWL_SYNTHETIC_SECRET", SECRET)
    script = (
        "import os,json; print(json.dumps({'exposed': int('PAWL_SYNTHETIC_SECRET' in os.environ)}))"
    )
    (tmp_path / "pawl.toml").write_text(
        f"[execution]\nenvironment={json.dumps(mode)}\npass_env={json.dumps(allowed)}\n"
        '[[metric]]\nname="exposure"\ndirection="down"\nextract="json:exposed"\ncommand='
        + json.dumps([sys.executable, "-c", script])
        + "\n"
    )
    (tmp_path / "pawl.baseline.json").write_text(
        json.dumps(
            {
                "pawl_baseline": 1,
                "suites": {},
                "metrics": {"exposure": {"value": 0, "direction": "down"}},
            }
        )
    )
    assert main(["--root", str(tmp_path), "check", "--json"]) == code
    printed = capsys.readouterr().out
    report = json.loads(printed)
    assert report["environment"]["mode"] == mode
    assert report["environment"]["pass_env"] == allowed
    assert report["environment"]["sandbox"] is False
    assert SECRET not in printed
    assert SECRET not in (tmp_path / ".pawl/last-report.json").read_text()


@pytest.mark.parametrize(
    "name",
    [
        "PYTHONPATH",
        "LD_PRELOAD",
        "AWS_SECRET_ACCESS_KEY",
        "GIT_CONFIG_COUNT",
        "PYTEST_ADDOPTS",
        "PAWL_TEST_ORDER",
    ],
)
def test_ambient_injection_dropped(
    name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(name, SECRET)
    result = run(
        [sys.executable, "-c", f"import os; print({name!r} in os.environ)"],
        tmp_path,
        10,
        limits=MINIMAL,
    )
    assert result.stdout.strip() == "False"
    assert SECRET not in result.stderr


def test_default_inherits_and_explicit_names_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PAWL_SYNTHETIC_SECRET", SECRET)
    script = "import os; print(os.environ.get('PAWL_SYNTHETIC_SECRET','absent'))"
    for limits in (ExecutionLimits(), replace(MINIMAL, pass_env=("PAWL_SYNTHETIC_SECRET",))):
        assert (
            run([sys.executable, "-c", script], tmp_path, 10, limits=limits).stdout.strip()
            == SECRET
        )


def test_fresh_home_and_temp_are_removed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original_home = tmp_path / "original-home"
    original_home.mkdir()
    (original_home / "credential").write_text(SECRET)
    monkeypatch.setenv("HOME", str(original_home))
    script = "import os,json; print(json.dumps({k:os.environ[k] for k in ('HOME','TMPDIR','TMP','TEMP')}))"
    homes = []
    for _ in range(2):
        result = run([sys.executable, "-c", script], tmp_path, 10, limits=MINIMAL)
        paths = json.loads(result.stdout)
        assert paths["HOME"] != str(original_home)
        assert paths["TMPDIR"] == paths["TMP"] == paths["TEMP"]
        assert all(not Path(path).exists() for path in paths.values())
        homes.append(paths["HOME"])
    assert homes[0] != homes[1]
    assert (original_home / "credential").read_text() == SECRET


def test_cleanup_after_timeout(tmp_path: Path) -> None:
    script = "import os,time; open('home','w').write(os.environ['HOME']); time.sleep(20)"
    with pytest.raises(ExecutionError, match="RUN_TIMEOUT"):
        run([sys.executable, "-c", script], tmp_path, 0.5, limits=MINIMAL)
    assert not Path((tmp_path / "home").read_text()).exists()


def test_environment_cleanup_failure_is_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from pawl import environment

    original = environment.tempfile.TemporaryDirectory.cleanup

    def failed(self):
        original(self)
        raise OSError("synthetic")

    monkeypatch.setattr(environment.tempfile.TemporaryDirectory, "cleanup", failed)
    with (
        pytest.raises(EnvironmentPolicyError, match="ENV_CLEANUP_FAILED"),
        command_environment("minimal", (), None),
    ):
        pass


@pytest.mark.parametrize(
    "body",
    [
        'environment="unknown"',
        "environment=true",
        'pass_env="TOKEN"',
        'pass_env=["*"]',
        'pass_env=["BAD=NAME"]',
        "pass_env=[true]",
        'pass_env=["HOME"]',
        'pass_env=["TMPDIR"]',
        'pass_env=["PAWL_TEST_ORDER"]',
        'pass_env=["TOKEN", "TOKEN"]',
    ],
)
def test_invalid_environment_policy(tmp_path: Path, body: str) -> None:
    with pytest.raises(ConfigError):
        parse_config(
            "[execution]\n" + body + '\n[[suite]]\nname="t"\nadapter="pytest"\ncommand="python"\n',
            tmp_path,
        )


def test_unapproved_runtime_override_fails(tmp_path: Path) -> None:
    with pytest.raises(EnvironmentPolicyError, match="unapproved"):
        run([sys.executable, "-c", "pass"], tmp_path, 10, {"TOKEN": SECRET}, limits=MINIMAL)


def test_preflight_uses_minimal_policy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAWL_SYNTHETIC_SECRET", SECRET)
    command = [sys.executable, "-c", "import os; assert 'PAWL_SYNTHETIC_SECRET' not in os.environ"]
    cfg = parse_config(
        '[execution]\nenvironment="minimal"\n[preflight]\ncommands=['
        + json.dumps(command)
        + "]\n"
        + '[[suite]]\nname="fixture"\nadapter="pytest"\ncommand="python"\n',
        tmp_path,
    )
    run_preflight(cfg)


def test_pytest_order_plugin_does_not_restore_ambient_pythonpath(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    injection = tmp_path / "injection"
    injection.mkdir()
    (injection / "ambient_module.py").write_text("VALUE=1")
    monkeypatch.setenv("PYTHONPATH", str(injection))
    monkeypatch.setenv("PAWL_TEST_ORDER", "random:999")
    (tmp_path / "test_order.py").write_text(
        "import os, importlib.util\n"
        "def test_first():\n"
        '    assert importlib.util.find_spec("ambient_module") is None\n'
        '    assert os.environ.get("PAWL_TEST_ORDER") in (None, "reverse")\n'
        "def test_second():\n    assert True\n"
    )
    suite = SuiteConfig("t", "pytest", (sys.executable, "-m", "pytest", "-q"), execution=MINIMAL)
    first = run_suite(suite, tmp_path, 0)
    reverse = run_suite(suite, tmp_path, 1)
    assert first.exit_code == reverse.exit_code == 0
    assert first.ids == reverse.ids and len(first.ids) == 2


def test_trusted_base_environment_cannot_be_weakened(
    demo_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from tests.conftest import commit, edit, git

    path = demo_repo / "pawl.toml"
    path.write_text(path.read_text() + '\n[execution]\nenvironment="minimal"\n')
    commit(demo_repo, "trusted minimal environment")
    git(demo_repo, "branch", "-f", "main", "HEAD")
    edit(path, 'environment="minimal"', 'environment="inherit"')
    monkeypatch.setenv("PAWL_SYNTHETIC_SECRET", SECRET)
    with (demo_repo / "calc/__init__.py").open("a") as stream:
        stream.write('\nimport os\nassert "PAWL_SYNTHETIC_SECRET" not in os.environ\n')
    assert main(["--root", str(demo_repo), "check", "--trusted-ref", "main", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["environment"]["mode"] == "minimal"
    assert SECRET not in json.dumps(report)


def test_minimal_policy_applies_during_base_test_replay(
    demo_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.conftest import commit, edit, git

    from pawl.config import load_config
    from pawl.guard import run_guard

    path = demo_repo / "pawl.toml"
    path.write_text(path.read_text() + '\n[execution]\nenvironment="minimal"\n')
    commit(demo_repo, "trusted minimal replay environment")
    git(demo_repo, "branch", "-f", "main", "HEAD")
    monkeypatch.setenv("PAWL_SYNTHETIC_SECRET", SECRET)
    with (demo_repo / "calc/__init__.py").open("a") as stream:
        stream.write('\nimport os\nassert "PAWL_SYNTHETIC_SECRET" not in os.environ\n')
    edit(
        demo_repo / "tests/test_calc.py",
        "def test_subtract():",
        "def test_subtract():\n    assert True",
    )
    result = run_guard(load_config(demo_repo), "main", replay=True)
    assert any(f.rule == "REPLAY_PASSED" for f in result.findings)
    assert not any(f.rule == "TESTS_WEAKENED_REPLAY" for f in result.findings)


def test_explicit_pythonpath_restored_only_when_requested(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    injection = tmp_path / "injection"
    injection.mkdir()
    (injection / "requested_module.py").write_text("VALUE=1")
    monkeypatch.setenv("PYTHONPATH", str(injection))
    (tmp_path / "test_explicit.py").write_text(
        "def test_requested():\n    import requested_module\n    assert requested_module.VALUE == 1\n"
    )
    suite = SuiteConfig(
        "t",
        "pytest",
        (sys.executable, "-m", "pytest", "-q"),
        execution=replace(MINIMAL, pass_env=("PYTHONPATH",)),
    )
    assert run_suite(suite, tmp_path, 1).exit_code == 0
