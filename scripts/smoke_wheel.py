#!/usr/bin/env python3
"""Exercise one hash-pinned wheel outside its source tree, without publishing.

This is local package evidence, not release authorization or a sandbox. Run it
only on trusted artifacts. The wheelhouse supplies pytest and its dependencies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path


def verified_wheel(path: Path, expected: str) -> bytes:
    if re.fullmatch(r"[0-9a-f]{64}", expected) is None:
        raise ValueError("expected SHA-256 must be 64 lowercase hex characters")
    if path.is_symlink() or not path.is_file() or path.suffix != ".whl":
        raise ValueError("wheel must be a regular .whl file, not a symlink")
    with path.open("rb") as stream:
        data = stream.read(64 * 1024 * 1024 + 1)
    if len(data) > 64 * 1024 * 1024:
        raise ValueError("wheel exceeds 64 MiB")
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("wheel SHA-256 mismatch")
    return data


def smoke(wheel: Path, digest: str, version: str, wheelhouse: Path) -> dict[str, object]:
    # Copy exactly the bytes checked here. A later path replacement cannot
    # silently change what pip installs.
    data = verified_wheel(wheel, digest)
    evidence: dict[str, object] = {
        "schema_version": 1,
        "kind": "local-wheel-smoke",
        "release_authorized": False,
        "wheel": wheel.name,
        "sha256": digest,
        "expected_version": version,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "checks": [],
    }
    checks: list[str] = []
    with tempfile.TemporaryDirectory(prefix="pawl-wheel-smoke-") as temporary:
        root = Path(temporary)
        artifact = root / wheel.name
        artifact.write_bytes(data)
        environment = root / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = environment / "bin/python"
        executable = environment / "bin/pawl"
        env = dict(os.environ)
        for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "PAWL_TEST_ORDER"):
            env.pop(key, None)
        env["PATH"] = f"{environment / 'bin'}{os.pathsep}{os.defpath}"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        customer = root / "customer"
        customer.mkdir()

        def run(argv: list[str], expected: int = 0) -> str:
            result = subprocess.run(
                argv,
                cwd=customer,
                env=env,
                text=True,
                capture_output=True,
                timeout=180,
                check=False,
            )
            if result.returncode != expected:
                raise RuntimeError(
                    f"{Path(argv[0]).name} {argv[1:]}: expected {expected}, "
                    f"got {result.returncode}\n{result.stdout}\n{result.stderr}"
                )
            return result.stdout

        pip = [str(python), "-I", "-m", "pip", "--isolated", "--disable-pip-version-check"]
        run([*pip, "install", "--no-index", "--no-deps", str(artifact)])
        run([*pip, "install", "--no-index", "--find-links", str(wheelhouse), "pytest==9.1.1"])
        run([*pip, "check"])
        installed = json.loads(
            run(
                [
                    str(python),
                    "-I",
                    "-c",
                    "import json, pawl; from importlib.metadata import version; "
                    "from pathlib import Path; "
                    "print(json.dumps([version('pawl-gate'), pawl.__version__, "
                    "pawl.__file__, Path(pawl.__file__).with_name('py.typed').is_file()]))",
                ]
            )
        )
        if installed[:2] != [version, version] or installed[3] is not True:
            raise ValueError("installed distribution/runtime version or py.typed mismatch")
        if not Path(installed[2]).is_relative_to(environment):
            raise ValueError("import did not resolve inside the fresh environment")
        checks.append("installed-metadata-and-import-origin")
        if version not in run([str(executable), "--version"]):
            raise ValueError("CLI version mismatch")
        run([str(executable), "--help"])
        checks.append("version-and-help")
        (customer / "app.py").write_text("def value():\n    return 2\n", encoding="utf-8")
        (customer / "test_app.py").write_text(
            "from app import value\n\ndef test_value():\n    assert value() == 2\n",
            encoding="utf-8",
        )
        run([str(executable), "init"])
        config = (customer / "pawl.toml").read_text(encoding="utf-8")
        if str(root) in config:
            raise ValueError("generated configuration contains the build host path")
        checks.append("portable-init")
        relocated = root / "relocated"
        shutil.copytree(customer, relocated)
        shutil.rmtree(customer)
        customer = relocated
        clean = json.loads(run([str(executable), "check", "--json"]))
        if clean["status"] != "pass":
            raise ValueError("clean customer did not pass")
        checks.append("relocated-clean-check")
        (customer / "app.py").write_text("def value():\n    return 0\n", encoding="utf-8")
        failed = json.loads(run([str(executable), "check", "--json"], expected=1))
        if failed["status"] != "fail":
            raise ValueError("regression was not reported as failure")
        checks.append("real-regression-rejected")
        report = run([str(executable), "report", "--format", "md"])
        if not report.strip():
            raise ValueError("regression report is empty")
        checks.append("markdown-report")
        (customer / "app.py").write_text("def value():\n    return 2\n", encoding="utf-8")
        run([str(executable), "check", "--json"])
        doctor = json.loads(run([str(executable), "doctor", "--json"]))
        if doctor["status"] != "ready":
            raise ValueError("offline local doctor is not ready")
        checks.append("recovery-and-local-doctor")
    evidence["checks"] = checks
    evidence["status"] = "pass"
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--wheelhouse", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    if args.receipt.exists():
        parser.error("receipt already exists; use a fresh path for each run")
    try:
        evidence = smoke(
            args.wheel.absolute(), args.sha256, args.version, args.wheelhouse.resolve()
        )
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"wheel smoke failed: {exc}", file=sys.stderr)
        return 1
    with args.receipt.open("x", encoding="utf-8") as stream:
        json.dump(evidence, stream, indent=2)
        stream.write("\n")
    print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
