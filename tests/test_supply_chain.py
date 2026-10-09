"""The workflow template pins Pawl by version and hash, in its own venv."""

from __future__ import annotations

import io
import json
import re
import tomllib
from pathlib import Path

import pytest

import pawl
from pawl import init as pawl_init
from pawl.cli import main
from pawl.errors import ConfigError
from pawl.templates import (
    GITHUB_WORKFLOW,
    PLACEHOLDER_SDIST,
    PLACEHOLDER_WHEEL,
    github_workflow,
)

ROOT = Path(__file__).resolve().parents[1]
WHEEL = "a" * 64
SDIST = "b" * 64


def test_versions_do_not_drift() -> None:
    """pyproject, __version__, the template, the integration file, and the docs agree."""
    version = pawl.__version__
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == version
    pin = f"pawl-gate=={version}"
    assert pin in GITHUB_WORKFLOW
    assert pin in (ROOT / "integrations" / "github" / "pawl.yml").read_text(encoding="utf-8")
    recommendation = (ROOT / "docs" / "RECOMMENDATION.md").read_text(encoding="utf-8")
    pins = set(re.findall(r"pawl-gate==([0-9][^\s\"']*)", recommendation))
    assert pins == {version}
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{version}]" in changelog


def test_template_installs_pawl_first_in_its_own_venv_by_hash() -> None:
    wf = github_workflow("9.9.9", WHEEL, SDIST)
    install = wf.index("Install Pawl")
    assert install < wf.index("Install the project")
    assert "pawl-gate==9.9.9" in wf
    assert f"--hash=sha256:{WHEEL}" in wf
    assert f"--hash=sha256:{SDIST}" in wf
    assert "--require-hashes --no-deps" in wf
    assert '"$RUNNER_TEMP/pawl-venv/bin/python" -m pip install' in wf
    # Every Pawl call uses the pinned binary, never a 'pawl' found on PATH.
    calls = re.findall(r"(\S*)\s+(?:check|guard|report) --", wf)
    assert calls
    assert set(calls) == {'"$PAWL"'}
    assert "pip install pawl-gate" not in wf
    assert '"pawl-gate==' not in wf


def test_integration_file_uses_placeholders_that_fail_closed() -> None:
    assert PLACEHOLDER_WHEEL in GITHUB_WORKFLOW
    assert PLACEHOLDER_SDIST in GITHUB_WORKFLOW
    assert not re.fullmatch(r"[0-9a-f]{64}", PLACEHOLDER_WHEEL)


class _Resp(io.BytesIO):
    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def _pypi(payload: object) -> object:
    def fake(url: str, timeout: float) -> _Resp:
        assert url == "https://pypi.org/pypi/pawl-gate/1.2.3/json"
        return _Resp(json.dumps(payload).encode())

    return fake


def test_pypi_hashes_reads_wheel_and_sdist(monkeypatch: pytest.MonkeyPatch) -> None:
    urls = [
        {"packagetype": "sdist", "digests": {"sha256": SDIST}},
        {"packagetype": "bdist_wheel", "digests": {"sha256": WHEEL}},
    ]
    monkeypatch.setattr(pawl_init.urllib.request, "urlopen", _pypi({"urls": urls}))
    assert pawl_init.pypi_hashes("1.2.3") == (WHEEL, SDIST)


def test_pypi_hashes_refuses_an_incomplete_release(monkeypatch: pytest.MonkeyPatch) -> None:
    urls = [{"packagetype": "bdist_wheel", "digests": {"sha256": WHEEL}}]
    monkeypatch.setattr(pawl_init.urllib.request, "urlopen", _pypi({"urls": urls}))
    with pytest.raises(ConfigError, match="no wheel and sdist"):
        pawl_init.pypi_hashes("1.2.3")


def _offline(url: str, timeout: float) -> _Resp:
    raise OSError("offline")


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_one.py").write_text("def test_one():\n    pass\n", encoding="utf-8")
    return repo


def test_init_github_pins_the_passed_hashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pawl_init.urllib.request, "urlopen", _offline)
    repo = _init_repo(tmp_path)
    args = ["--root", str(repo), "init", "--runner", "pytest", "--github", "--skip-preflight"]
    assert main([*args, "--wheel-sha256", WHEEL, "--sdist-sha256", SDIST]) == 0
    wf = (repo / ".github" / "workflows" / "pawl.yml").read_text(encoding="utf-8")
    assert wf == github_workflow(pawl.__version__, WHEEL, SDIST)


def test_init_github_offline_writes_placeholders_and_warns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(pawl_init.urllib.request, "urlopen", _offline)
    repo = _init_repo(tmp_path)
    args = ["--root", str(repo), "init", "--runner", "pytest", "--github", "--skip-preflight"]
    assert main(args) == 0
    wf = (repo / ".github" / "workflows" / "pawl.yml").read_text(encoding="utf-8")
    assert wf == GITHUB_WORKFLOW
    assert "placeholder hashes" in capsys.readouterr().out


def test_init_rejects_a_malformed_hash(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    with pytest.raises(SystemExit):
        main(["--root", str(repo), "init", "--github", "--wheel-sha256", "abc"])


def test_init_requires_both_hashes(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    args = ["--root", str(repo), "init", "--runner", "pytest", "--github", "--skip-preflight"]
    assert main([*args, "--wheel-sha256", WHEEL]) == 2
    assert main([*args, "--sdist-sha256", SDIST]) == 2
    assert not (repo / "pawl.toml").exists()
    assert not (repo / ".github").exists()
