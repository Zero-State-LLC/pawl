from __future__ import annotations

from pathlib import Path

import pytest
from tests.conftest import commit, edit

from pawl.baseline import Baseline, SuiteBaseline
from pawl.config import Config, SuiteConfig, load_config
from pawl.guard import run_guard
from pawl.replay_scope import narrow_replay


def _suite_config(
    name: str = "tests",
    adapter: str = "pytest",
    command: tuple[str, ...] = ("python", "-m", "pytest", "tests", "-q"),
    identity: str = "ids",
    cwd: str = ".",
) -> SuiteConfig:
    return SuiteConfig(
        name=name,
        adapter=adapter,
        command=command,
        identity=identity,
        cwd=cwd,
    )


def _suite_baseline(
    *,
    identity: str = "ids",
    collected_ids: list[str] | None = None,
    failing_ids: list[str] | None = None,
    skipped_ids: list[str] | None = None,
    order_dependent: list[str] | None = None,
    collected: int = 0,
) -> SuiteBaseline:
    ids = list(collected_ids or [])
    return SuiteBaseline(
        identity=identity,
        collected=collected,
        collected_ids=ids,
        failing_ids=list(failing_ids or []),
        skipped_ids=list(skipped_ids or []),
        order_dependent=list(order_dependent or []),
    )


def _baseline(suites: dict[str, SuiteBaseline]) -> Baseline:
    return Baseline(suites=suites, metrics={}, quarantine=[], updated="2024-01-01T00:00:00Z")


TEST_IDS = [
    "tests/test_a.py::test_one",
    "tests/test_a.py::test_two",
    "tests/test_b.py::test_three",
]


def _default_config() -> Config:
    return Config(root=Path("/repo"), suites=(_suite_config(),))


def _default_baseline() -> Baseline:
    return _baseline(
        {
            "tests": _suite_baseline(
                collected_ids=TEST_IDS,
                failing_ids=["tests/test_a.py::test_two"],
                skipped_ids=["tests/test_b.py::test_three"],
                collected=3,
            )
        }
    )


def test_narrows_to_changed_test_file() -> None:
    result = narrow_replay(_default_config(), _default_baseline(), ["tests/test_a.py"])
    assert result is not None
    config, baseline = result

    assert config.suites[0].command == ("python", "-m", "pytest", "-q", "tests/test_a.py")
    assert config.suites[0].check_orders == 1

    sb = baseline.suites["tests"]
    assert sb.collected_ids == [
        "tests/test_a.py::test_one",
        "tests/test_a.py::test_two",
    ]
    assert sb.failing_ids == ["tests/test_a.py::test_two"]
    assert sb.skipped_ids == []
    assert sb.collected == 2
    assert baseline.metrics == {}


@pytest.mark.parametrize(
    "paths",
    [
        [],
        ["tests/conftest.py"],
        ["tests/helpers.py"],
        ["tests/test_new.py"],
    ],
)
def test_returns_none_when_unscopable(paths: list[str]) -> None:
    assert narrow_replay(_default_config(), _default_baseline(), paths) is None


def test_returns_none_for_non_pytest_adapter() -> None:
    config = Config(root=Path("/repo"), suites=(_suite_config(adapter="jest"),))
    assert narrow_replay(config, _default_baseline(), ["tests/test_a.py"]) is None


def test_returns_none_for_count_identity() -> None:
    baseline = _baseline(
        {
            "tests": _suite_baseline(
                identity="count",
                collected_ids=TEST_IDS,
                collected=3,
            )
        }
    )
    assert narrow_replay(_default_config(), baseline, ["tests/test_a.py"]) is None


def test_suite_cwd_prefix_is_stripped() -> None:
    config = Config(root=Path("/repo"), suites=(_suite_config(cwd="pkg"),))
    baseline = _baseline(
        {
            "tests": _suite_baseline(
                collected_ids=["tests/test_a.py::test_one"],
                collected=1,
            )
        }
    )
    result = narrow_replay(config, baseline, ["pkg/tests/test_a.py"])
    assert result is not None
    narrowed_config, narrowed_baseline = result
    assert narrowed_config.suites[0].command[-1] == "tests/test_a.py"
    assert narrowed_baseline.suites["tests"].collected_ids == ["tests/test_a.py::test_one"]


def test_suite_without_changed_files_is_dropped() -> None:
    config = Config(
        root=Path("/repo"),
        suites=(
            _suite_config(),
            _suite_config(
                name="holdout",
                command=("python", "-m", "pytest", "holdout", "-q"),
            ),
        ),
    )
    baseline = _baseline(
        {
            "tests": _suite_baseline(collected_ids=TEST_IDS, collected=3),
            "holdout": _suite_baseline(
                collected_ids=["holdout/test_h.py::test_h"],
                collected=1,
            ),
        }
    )
    result = narrow_replay(config, baseline, ["tests/test_b.py"])
    assert result is not None
    narrowed_config, _ = result
    assert [suite.name for suite in narrowed_config.suites] == ["tests"]


@pytest.mark.slow
def test_replay_narrowed_when_tests_still_pass(demo_repo: Path) -> None:
    edit(
        demo_repo / "tests" / "test_calc.py",
        "assert add(2, 3) == 5",
        "assert add(3, 2) == 5",
    )
    commit(demo_repo, "tweak add assertion")

    report = run_guard(load_config(demo_repo), "main", replay=True)
    messages = [f.message for f in report.findings if f.rule == "REPLAY_PASSED"]
    assert messages, [f.rule for f in report.findings]
    assert any("1 changed test file(s)" in message for message in messages)


@pytest.mark.slow
def test_replay_still_catches_weakened_test(demo_repo: Path) -> None:
    edit(demo_repo / "calc" / "__init__.py", "return a + b", "return a * b")
    edit(
        demo_repo / "tests" / "test_calc.py",
        "assert add(2, 3) == 5",
        "assert add(2, 3) == 6",
    )
    edit(
        demo_repo / "tests" / "test_calc.py",
        "assert add(-2, -3) == -5",
        "assert add(-2, -3) == 6",
    )
    commit(demo_repo, "weaken add assertions")

    report = run_guard(load_config(demo_repo), "main", replay=True)
    weakened = [f for f in report.findings if f.rule == "TESTS_WEAKENED_REPLAY"]
    assert weakened, [f.rule for f in report.findings]
    assert any("tests/test_calc.py::test_add" in f.ids for f in weakened)
