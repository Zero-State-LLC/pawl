from __future__ import annotations

import hashlib
import runpy
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest


def verifier() -> Callable[[Path, str], bytes]:
    script = Path(__file__).parents[1] / "scripts/smoke_wheel.py"
    return cast(Callable[[Path, str], bytes], runpy.run_path(str(script))["verified_wheel"])


def test_wheel_hash_pins_copied_bytes(tmp_path: Path) -> None:
    wheel = tmp_path / "example.whl"
    wheel.write_bytes(b"original")
    digest = hashlib.sha256(b"original").hexdigest()
    checked = verifier()(wheel, digest)
    wheel.write_bytes(b"changed")
    assert checked == b"original"
    with pytest.raises(ValueError, match="mismatch"):
        verifier()(wheel, digest)


@pytest.mark.parametrize("digest", ["", "z" * 64, "a" * 63], ids=["empty", "not-hex", "short"])
def test_wheel_invalid_expected_hash_rejected(tmp_path: Path, digest: str) -> None:
    with pytest.raises(ValueError, match="lowercase hex"):
        verifier()(tmp_path / "absent.whl", digest)


def test_wheel_symlink_rejected(tmp_path: Path) -> None:
    target = tmp_path / "real.whl"
    target.write_bytes(b"original")
    link = tmp_path / "link.whl"
    link.symlink_to(target)
    with pytest.raises(ValueError, match="symlink"):
        verifier()(link, hashlib.sha256(b"original").hexdigest())
