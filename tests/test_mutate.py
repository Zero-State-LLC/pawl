from __future__ import annotations

from pathlib import Path

import pytest

from pawl.mutate import changed_lines, generate


def test_changed_lines() -> None:
    diff = "@@ -1,2 +3,2 @@\n x\n+y\n@@ -10 +20,0 @@\n-z\n"
    assert changed_lines(diff) == {4}


def test_generate_mutants(tmp_path: Path) -> None:
    src = tmp_path / "m.py"
    src.write_text("def f(a, b):\n    if a < b and a > 0:\n        return a + 1\n    return b\n")
    mutants = generate(src, "m.py", {2, 3})
    descs = {m.description for m in mutants}
    assert any(d.startswith("Lt") for d in descs)
    assert any(d.startswith("Add") for d in descs)
    assert all(m.line in (2, 3) for m in mutants)
    assert all(m.source != src.read_text() for m in mutants)


def test_mutation_candidates_stay_under_a_subdirectory_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from tests.conftest import commit, git

    from pawl import mutate
    from pawl.config import load_config

    repo = tmp_path / "mono"
    (repo / "pkg" / "tests").mkdir(parents=True)
    (repo / "sibling").mkdir()
    (repo / "pkg" / "pawl.toml").write_text(
        '[[suite]]\nname = "t"\nadapter = "pytest"\ncommand = ["true"]\n', encoding="utf-8"
    )
    git(repo, "init", "-q", "-b", "main")
    (repo / "README").write_text("x\n", encoding="utf-8")
    commit(repo, "base")
    git(repo, "checkout", "-q", "-b", "agent")
    body = "def f(a, b):\n    return a + b\n"
    for rel in ("pkg/app.py", "pkg/tests/helper.py", "sibling/other.py"):
        (repo / rel).write_text(body, encoding="utf-8")
    commit(repo, "change")
    ran = SimpleNamespace(failing=set(), collected=1)
    monkeypatch.setattr(mutate, "run_suite", lambda suite, root: ran)
    mutants = mutate.run_mutation(load_config(repo / "pkg"), "main", 50)
    assert mutants
    assert {m.path for m in mutants} == {"pkg/app.py"}
