from __future__ import annotations

from pathlib import Path

import pytest

from pawl.config import parse_config
from pawl.errors import ConfigError

MINIMAL = """
[[suite]]
name = "tests"
adapter = "pytest"
command = "python -m pytest -q"
"""


def test_minimal_config_defaults() -> None:
    cfg = parse_config(MINIMAL, Path("/x"))
    suite = cfg.suites[0]
    assert suite.command == ("python", "-m", "pytest", "-q")
    assert suite.identity == "ids"
    assert cfg.lock_in_ci is True
    assert "pawl.baseline.json" in cfg.guard.protected
    assert cfg.baseline_path == Path("/x/pawl.baseline.json")


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", "at least one"),
        ("[[suite]]\nname='a'\nadapter='nope'\ncommand='x'", "adapter"),
        ("[[suite]]\nname='a'\nadapter='junit'\ncommand='x'", "junit_path"),
        ("[[suite]]\nname='a'\nadapter='pytest'\ncommand='x'\nbogus=1", "unknown key"),
        ("[[suite]]\nname='a'\nadapter='pytest'\ncommand=''", "empty"),
        ("[[suite]]\nname='a'\nadapter='pytest'\ncommand='x'\nidentity='maybe'", "identity"),
        (MINIMAL + MINIMAL, "unique"),
        (
            "[[metric]]\nname='m'\ncommand='x'\ndirection='sideways'\nextract='count-lines'",
            "direction",
        ),
        ("[[metric]]\nname='m'\ncommand='x'\ndirection='down'\nextract='magic'", "extract"),
        ("not toml = = =", "invalid TOML"),
        ("[surprise]\n" + MINIMAL, "unknown key"),
    ],
)
def test_invalid_configs_fail_closed(text: str, message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        parse_config(text, Path("/x"))


def test_guard_extra_protected_and_preflight() -> None:
    text = (
        MINIMAL
        + """
[guard]
extra_protected = ["scripts/gate.sh"]
fail_on_suspicious = true

[preflight]
imports = [{ module = "calc", expect_under = "src" }]
commands = [["true"]]
"""
    )
    cfg = parse_config(text, Path("/x"))
    assert "scripts/gate.sh" in cfg.guard.protected
    assert cfg.guard.fail_on_suspicious
    assert cfg.preflight.imports[0].expect_under == "src"
    assert cfg.preflight.commands == (("true",),)
