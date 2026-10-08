from __future__ import annotations

import sys
from pathlib import Path

import pytest

from pawl.config import parse_config
from pawl.errors import PreflightError
from pawl.preflight import run_preflight


def cfg(tmp_path: Path, body: str):  # type: ignore[no-untyped-def]
    return parse_config('[[suite]]\nname="t"\nadapter="pytest"\ncommand="x"\n' + body, tmp_path)


def test_import_resolves_under_root(tmp_path: Path) -> None:
    (tmp_path / "mypkg").mkdir()
    (tmp_path / "mypkg" / "__init__.py").write_text("")
    c = cfg(
        tmp_path,
        f'[preflight]\npython = "{sys.executable}"\n[[preflight.imports]]\nmodule = "mypkg"\nexpect_under = "."\n',
    )
    notes = run_preflight(c)
    assert any("mypkg" in n for n in notes)


def test_import_resolving_elsewhere_fails(tmp_path: Path) -> None:
    c = cfg(
        tmp_path,
        f'[preflight]\npython = "{sys.executable}"\n[[preflight.imports]]\nmodule = "json"\nexpect_under = "."\n',
    )
    with pytest.raises(PreflightError, match="not under"):
        run_preflight(c)


def test_missing_module_fails(tmp_path: Path) -> None:
    c = cfg(
        tmp_path,
        f'[preflight]\npython = "{sys.executable}"\n[[preflight.imports]]\nmodule = "no_such_mod_xyz"\n',
    )
    with pytest.raises(PreflightError):
        run_preflight(c)


def test_preflight_command(tmp_path: Path) -> None:
    ok = cfg(tmp_path, '[preflight]\ncommands = ["true"]\n')
    run_preflight(ok)
    bad = cfg(tmp_path, '[preflight]\ncommands = ["false"]\n')
    with pytest.raises(PreflightError):
        run_preflight(bad)
