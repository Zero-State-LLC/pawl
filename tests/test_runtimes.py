"""End-to-end adapter runs against real toolchains. Skipped when a toolchain is absent."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from pawl.cli import main


def init_and_check(root: Path, runner: str) -> tuple[int, dict]:  # type: ignore[type-arg]
    assert main(["--root", str(root), "init", "--runner", runner, "--skip-preflight"]) == 0
    data = json.loads((root / "pawl.baseline.json").read_text())
    return main(["--root", str(root), "check", "--skip-preflight"]), data


@pytest.mark.skipif(shutil.which("go") is None, reason="go not installed")
def test_go_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOFLAGS", "-mod=mod")
    monkeypatch.setenv("GOCACHE", str(tmp_path / "gocache"))
    (tmp_path / "go.mod").write_text("module example.com/demo\n\ngo 1.20\n")
    (tmp_path / "calc.go").write_text("package demo\n\nfunc Add(a, b int) int { return a + b }\n")
    test = tmp_path / "calc_test.go"
    test.write_text(
        'package demo\n\nimport "testing"\n\n'
        'func TestAdd(t *testing.T) { if Add(2, 3) != 5 { t.Fatal("bad") } }\n'
        'func TestAddZero(t *testing.T) { if Add(0, 0) != 0 { t.Fatal("bad") } }\n'
    )
    code, data = init_and_check(tmp_path, "go")
    assert code == 0
    assert data["suites"]["tests"]["collected"] == 2
    (tmp_path / "calc.go").write_text("package demo\n\nfunc Add(a, b int) int { return a * b }\n")
    assert main(["--root", str(tmp_path), "check", "--skip-preflight"]) == 1


@pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not installed")
def test_cargo_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CARGO_TARGET_DIR", str(tmp_path / "target"))
    monkeypatch.setenv("CARGO_NET_OFFLINE", "true")
    (tmp_path / "Cargo.toml").write_text(
        '[package]\nname = "demo"\nversion = "0.1.0"\nedition = "2021"\n'
    )
    (tmp_path / "src").mkdir()
    lib = tmp_path / "src" / "lib.rs"
    body = (
        "pub fn add(a: i32, b: i32) -> i32 {{ {} }}\n"
        "#[cfg(test)]\nmod tests {{\n    use super::*;\n"
        "    #[test]\n    fn adds() {{ assert_eq!(add(2, 3), 5); }}\n"
        "    #[test]\n    fn zero() {{ assert_eq!(add(0, 0), 0); }}\n}}\n"
    )
    lib.write_text(body.format("a + b"))
    code, data = init_and_check(tmp_path, "cargo")
    assert code == 0
    assert data["suites"]["tests"]["collected"] >= 2
    lib.write_text(body.format("a * b"))
    assert main(["--root", str(tmp_path), "check", "--skip-preflight"]) == 1


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_generic_junit_with_node_test_runner(tmp_path: Path) -> None:
    (tmp_path / "pawl.toml").write_text(
        "[[suite]]\n"
        'name = "node"\n'
        'adapter = "junit"\n'
        'command = ["node", "--test", "--test-reporter=junit", '
        '"--test-reporter-destination=report.xml", "calc.test.js"]\n'
        'junit_path = "report.xml"\n'
    )
    src = (
        'const test = require("node:test");\n'
        'const assert = require("node:assert");\n'
        'test("adds", () => assert.equal(1 + 1, {}));\n'
        'test("subtracts", () => assert.equal(3 - 1, 2));\n'
    )
    (tmp_path / "calc.test.js").write_text(src.format(2))
    root = ["--root", str(tmp_path)]
    assert main([*root, "update", "--skip-preflight"]) == 0
    assert main([*root, "check", "--skip-preflight"]) == 0
    (tmp_path / "calc.test.js").write_text(src.format(3))
    assert main([*root, "check", "--skip-preflight"]) == 1
