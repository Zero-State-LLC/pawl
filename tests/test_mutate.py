from __future__ import annotations

from pathlib import Path

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
