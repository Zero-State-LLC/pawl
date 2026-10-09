"""Count TODO/FIXME comments in the demo ``calc`` package.

Only comments count: a TODO inside a string or docstring is ignored. A file
that does not parse makes this tool crash, which is intentional: the Pawl
metric treats a crash as an error rather than as zero findings.
"""

from __future__ import annotations

import ast
import io
import tokenize
from pathlib import Path


def python_files(root: Path) -> list[Path]:
    """Return every ``*.py`` file under ``root``, sorted by path."""
    return sorted(root.rglob("*.py"))


def findings(path: Path) -> list[str]:
    """Return one formatted line per TODO/FIXME comment in ``path``."""
    with tokenize.open(path) as handle:
        source = handle.read()
    ast.parse(source, filename=str(path))
    formatted: list[str] = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type != tokenize.COMMENT:
            continue
        if "TODO" not in token.string and "FIXME" not in token.string:
            continue
        text = token.string.strip()
        line = f"{path.as_posix()}:{token.start[0]}:{token.start[1] + 1}: T001 {text}"
        formatted.append(line)
    return formatted


def main() -> int:
    """Print every TODO/FIXME comment under ``calc`` and return 0."""
    for path in python_files(Path("calc")):
        for line in findings(path):
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
