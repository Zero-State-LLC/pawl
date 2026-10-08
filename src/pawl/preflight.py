"""Preflight: refuse to measure in the wrong environment.

The Abraxas incident: a stale editable install made ``core`` resolve to another
checkout, so 28 test modules failed to collect and the run looked like a broken
repo. A gate measured in the wrong environment can also look green when it is
not. Preflight fails closed before any suite runs.
"""

from __future__ import annotations

import json
from pathlib import Path

from pawl.config import Config
from pawl.errors import PreflightError
from pawl.runner import run

_PROBE = r"""
import importlib.util, json, os, sys
spec = importlib.util.find_spec(sys.argv[1])
locs = []
if spec is not None:
    locs = list(spec.submodule_search_locations or [])
    if spec.origin and spec.origin not in ("namespace", "built-in", "frozen"):
        if spec.submodule_search_locations:
            locs.append(spec.origin)
        else:
            locs.append(os.path.dirname(spec.origin))
real = [os.path.realpath(p) for p in locs]
print(json.dumps({"found": spec is not None, "locations": real, "python": sys.executable}))
"""


def run_preflight(config: Config) -> list[str]:
    """Run all preflight checks. Returns notes; raises PreflightError on failure."""
    notes: list[str] = []
    pf = config.preflight
    for check in pf.imports:
        done = run([pf.python, "-c", _PROBE, check.module], config.root, 120)
        if done.returncode != 0:
            raise PreflightError(f"preflight: could not probe {check.module}:\n{done.tail()}")
        data = json.loads(done.stdout.strip().splitlines()[-1])
        want = (config.root / check.expect_under).resolve()
        locations = [Path(p) for p in data["locations"]]
        ok = data["found"] and all(_under(p, want) for p in locations) and locations
        if not ok:
            raise PreflightError(
                f"preflight: '{check.module}' resolves to {data['locations'] or 'nothing'} "
                f"with {data['python']}, not under {want}. Wrong interpreter or a stale "
                "install. Fix the environment; do not change the baseline."
            )
        notes.append(f"preflight: {check.module} resolves under {check.expect_under}")
    for argv in pf.commands:
        done = run(argv, config.root, 600)
        if done.returncode != 0:
            raise PreflightError(f"preflight command failed: {' '.join(argv)}\n{done.tail()}")
        notes.append(f"preflight: {' '.join(argv)} ok")
    return notes


def _under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root)
    except ValueError:
        return False
    return True
