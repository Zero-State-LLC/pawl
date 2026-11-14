from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

import pawl.init as init_module
from pawl.cli import main
from pawl.errors import ConfigError, PawlError
from pawl.init import render_config
from pawl.init_transaction import commit_files


def project(path: Path) -> Path:
    (path / "tests").mkdir(parents=True)
    (path / "tests/test_one.py").write_text("def test_one():\n    assert 1 == 1\n")
    return path


def owned(root: Path) -> dict[str, bytes]:
    names = ("pawl.toml", "pawl.baseline.json", "PAWL_DEBT.md", ".github/workflows/pawl.yml")
    return {name: (root / name).read_bytes() for name in names if (root / name).exists()}


def test_default_config_is_portable(tmp_path: Path) -> None:
    config = render_config(project(tmp_path / "project"), "pytest")
    assert 'command = ["python", "-m", "pytest", "-q"]' in config
    assert sys.executable not in config


def test_explicit_interpreter_and_nonportable_diagnostic(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = project(tmp_path / "project")
    assert main(["--root", str(root), "init", "--python", sys.executable]) == 0
    assert "nonportable" in capsys.readouterr().out
    assert sys.executable in (root / "pawl.toml").read_text()


def test_target_path_survives_relocation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = project(tmp_path / "host-a")
    original_path = os.environ["PATH"]
    for host in ("a", "b"):
        bindir = tmp_path / host / "bin"
        bindir.mkdir(parents=True)
        marker = tmp_path / f"used-{host}"
        python = bindir / "python"
        python.write_text(f'#!/bin/sh\ntouch "{marker}"\nexec "{sys.executable}" "$@"\n')
        python.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path / 'a/bin'}:{original_path}")
    assert main(["--root", str(root), "init"]) == 0
    clone = tmp_path / "host-b"
    shutil.copytree(root, clone, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    shutil.rmtree(tmp_path / "a")
    monkeypatch.setenv("PATH", f"{tmp_path / 'b/bin'}:{original_path}")
    assert main(["--root", str(clone), "check"]) == 0
    assert (tmp_path / "used-b").is_file()
    assert str(tmp_path) not in (clone / "pawl.toml").read_text()


def test_missing_target_returns_preflight_without_writes(tmp_path: Path) -> None:
    root = project(tmp_path / "project")
    assert main(["--root", str(root), "init", "--python", "pawl-no-such-python"]) == 3
    assert owned(root) == {}


def test_missing_pytest_returns_preflight_without_writes(tmp_path: Path) -> None:
    root = project(tmp_path / "project")
    python = tmp_path / "no-pytest"
    python.write_text("#!/bin/sh\nexit 1\n")
    python.chmod(0o755)
    assert main(["--root", str(root), "init", "--python", str(python)]) == 3
    assert owned(root) == {}


def offline(version: str, timeout: float = 10.0) -> tuple[str, str]:
    raise ConfigError("offline")


def test_offline_hash_failure_preserves_existing_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(tmp_path / "project")
    (root / "pawl.toml").write_text("original config\n")
    (root / "pawl.baseline.json").write_text("original baseline\n")
    before = owned(root)
    monkeypatch.setattr(init_module, "pypi_hashes", offline)
    assert main(["--root", str(root), "init", "--github", "--force"]) == 2
    assert owned(root) == before
    assert not (root / ".github").exists()


def test_offline_explicit_hashes_complete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = project(tmp_path / "project")
    monkeypatch.setattr(init_module, "pypi_hashes", offline)
    assert (
        main(
            [
                "--root",
                str(root),
                "init",
                "--github",
                "--wheel-sha256",
                "a" * 64,
                "--sdist-sha256",
                "b" * 64,
            ]
        )
        == 0
    )
    assert len(owned(root)) == 4
    assert "a" * 64 in (root / ".github/workflows/pawl.yml").read_text()


def test_collection_failure_leaves_no_setup(tmp_path: Path) -> None:
    root = project(tmp_path / "project")
    (root / "tests/test_one.py").write_text("raise RuntimeError('cannot collect')\n")
    assert main(["--root", str(root), "init"]) == 2
    assert owned(root) == {}


@pytest.mark.parametrize("name", ["pawl.baseline.json", ".github/workflows/pawl.yml"])
def test_existing_output_requires_force(tmp_path: Path, name: str) -> None:
    root = project(tmp_path / "project")
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("keep me")
    args = ["--github", "--wheel-sha256", "a" * 64, "--sdist-sha256", "b" * 64]
    assert main(["--root", str(root), "init", *args]) == 2
    assert owned(root) == {name: b"keep me"}


def test_transaction_rolls_back_new_files_and_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = os.replace

    def fail_second(src: object, dst: object) -> None:
        if Path(str(dst)).name == "second":
            raise OSError("simulated write failure")
        original(src, dst)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "replace", fail_second)
    with pytest.raises(PawlError, match="rolled back"):
        commit_files(tmp_path, {"first": b"1", "nested/second": b"2"}, force=False, append="debt")
    assert list(tmp_path.iterdir()) == []


def test_transaction_restores_bytes_and_modes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = tmp_path / "first"
    first.write_bytes(b"original")
    first.chmod(0o600)
    original = os.replace

    def fail_second(src: object, dst: object) -> None:
        if Path(str(dst)).name == "second":
            raise OSError("simulated write failure")
        original(src, dst)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "replace", fail_second)
    with pytest.raises(PawlError, match="rolled back"):
        commit_files(tmp_path, {"first": b"new", "second": b"2"}, force=True, append="debt")
    assert first.read_bytes() == b"original"
    assert first.stat().st_mode & 0o777 == 0o600
    assert sorted(p.name for p in tmp_path.iterdir()) == ["first"]


def test_symlink_destination_refused(tmp_path: Path) -> None:
    target = tmp_path / "outside"
    target.write_text("unchanged")
    (tmp_path / "config").symlink_to(target)
    with pytest.raises(PawlError, match="linked"):
        commit_files(tmp_path, {"config": b"changed"}, force=True, append="debt")
    assert target.read_text() == "unchanged"
