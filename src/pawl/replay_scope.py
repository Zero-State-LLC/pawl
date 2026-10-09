"""Narrow a Pawl replay to the changed test files.

The helper in this module inspects a set of changed paths and, when every path is
a pytest test file that can be attributed to a suite present in the baseline,
returns a narrowed ``Config`` and ``Baseline`` targeting only those files.
Otherwise it returns ``None`` to signal that the full replay should run.
"""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import PurePosixPath

from pawl.adapters import _pytest_base
from pawl.baseline import Baseline, SuiteBaseline
from pawl.config import Config, SuiteConfig

TEST_FILE = re.compile(r"(?:^|/)(?:test_[^/]*|[^/]*_test)\.py$")


def _file_of_id(identifier: str) -> str:
    """Return the file portion of a node id, before the first ``::`` separator."""
    return identifier.split("::", 1)[0]


def _filter_ids(identifiers: list[str], files: set[str]) -> list[str]:
    """Keep identifiers whose file portion is one of the given suite files."""
    return [identifier for identifier in identifiers if _file_of_id(identifier) in files]


def narrow_replay(
    config: Config, baseline: Baseline, paths: list[str]
) -> tuple[Config, Baseline] | None:
    """Restrict a replay to the changed test files, or return None to run everything."""
    if not paths:
        return None
    if any(TEST_FILE.search(path) is None for path in paths):
        return None

    suite_map: dict[str, tuple[SuiteConfig, SuiteBaseline]] = {}
    prefixes: dict[str, str] = {}
    for suite in config.suites:
        if suite.adapter != "pytest":
            return None
        sb = baseline.suites.get(suite.name)
        if sb is None or sb.identity != "ids":
            return None
        suite_map[suite.name] = (suite, sb)
        cwd = PurePosixPath(suite.cwd)
        prefixes[suite.name] = "" if str(cwd) == "." else str(cwd) + "/"

    selected: dict[str, set[str]] = {name: set() for name in suite_map}
    covered: set[int] = set()
    for suite in config.suites:
        sb = suite_map[suite.name][1]
        prefix = prefixes[suite.name]
        collected_ids = sb.collected_ids
        for index, path in enumerate(paths):
            if not path.startswith(prefix):
                continue
            relative = path[len(prefix) :]
            marker = relative + "::"
            if any(identifier.startswith(marker) for identifier in collected_ids):
                selected[suite.name].add(relative)
                covered.add(index)

    if len(covered) != len(paths):
        return None

    new_suites: list[SuiteConfig] = []
    new_baselines: dict[str, SuiteBaseline] = {}
    for suite in config.suites:
        files = selected[suite.name]
        if not files:
            continue
        sb = suite_map[suite.name][1]
        sorted_files = sorted(files)
        command = tuple(_pytest_base(suite.command)) + tuple(sorted_files)
        new_suites.append(replace(suite, command=command, check_orders=1))
        markers = set(sorted_files)
        collected_ids = _filter_ids(sb.collected_ids, markers)
        new_baselines[suite.name] = replace(
            sb,
            failing_ids=_filter_ids(sb.failing_ids, markers),
            collected=len(collected_ids),
            collected_ids=collected_ids,
            skipped_ids=_filter_ids(sb.skipped_ids, markers),
            order_dependent=_filter_ids(sb.order_dependent, markers),
        )

    new_baseline = Baseline(
        suites=new_baselines,
        metrics={},
        quarantine=list(baseline.quarantine),
        updated=baseline.updated,
    )
    new_config = replace(config, suites=tuple(new_suites))
    return new_config, new_baseline
