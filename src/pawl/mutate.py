"""Advisory mutation spot check on changed Python lines.

Weak tests let wrong patches pass (UTBoost https://arxiv.org/abs/2506.09289,
PatchDiff https://arxiv.org/abs/2503.15223), and LLM-written tests often have
little discriminative power (SWE-Mutation https://arxiv.org/abs/2605.22175).
A few mutants on the lines an agent changed show whether any test notices.
This command never gates by default; it reports.
"""

from __future__ import annotations

import ast
import copy
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from pawl.adapters import run_suite
from pawl.config import Config
from pawl.errors import ParseError, PawlError
from pawl.gitutil import changed_files, diff_text, merge_base, prefix, toplevel
from pawl.guard import matches_any, root_relative

_SWAP_CMP: dict[type, type] = {
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
    ast.Lt: ast.GtE,
    ast.GtE: ast.Lt,
    ast.Gt: ast.LtE,
    ast.LtE: ast.Gt,
    ast.Is: ast.IsNot,
    ast.IsNot: ast.Is,
    ast.In: ast.NotIn,
    ast.NotIn: ast.In,
}
_SWAP_BIN: dict[type, type] = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.FloorDiv}


@dataclass
class Mutant:
    path: str
    line: int
    description: str
    source: str
    status: str = "pending"  # killed | survived | error


def changed_lines(diff: str) -> set[int]:
    """Line numbers (in the new file) of added or changed lines in a unified diff."""
    lines: set[int] = set()
    current = 0
    for raw in diff.splitlines():
        m = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", raw)
        if m:
            current = int(m.group(1))
            continue
        if not current or raw.startswith(("+++", "---")):
            continue
        if raw.startswith("+"):
            lines.add(current)
            current += 1
        elif raw.startswith(" "):
            current += 1
    return lines


def _candidates(
    tree: ast.AST, lines: set[int]
) -> Iterator[tuple[int, str, Callable[[ast.AST], None]]]:
    for idx, node in enumerate(ast.walk(tree)):
        line = getattr(node, "lineno", None)
        if line not in lines:
            continue
        if isinstance(node, ast.Compare) and type(node.ops[0]) in _SWAP_CMP:
            new_op = _SWAP_CMP[type(node.ops[0])]

            def apply_cmp(n: ast.AST, op: type = new_op) -> None:
                assert isinstance(n, ast.Compare)
                n.ops[0] = op()

            yield idx, f"{type(node.ops[0]).__name__} -> {new_op.__name__}", apply_cmp
        elif isinstance(node, ast.BinOp) and type(node.op) in _SWAP_BIN:
            new_bin = _SWAP_BIN[type(node.op)]

            def apply_bin(n: ast.AST, op: type = new_bin) -> None:
                assert isinstance(n, ast.BinOp)
                n.op = op()

            yield idx, f"{type(node.op).__name__} -> {new_bin.__name__}", apply_bin
        elif isinstance(node, ast.BoolOp):

            def apply_bool(n: ast.AST) -> None:
                assert isinstance(n, ast.BoolOp)
                n.op = ast.Or() if isinstance(n.op, ast.And) else ast.And()

            yield idx, "and <-> or", apply_bool
        elif isinstance(node, ast.Constant) and type(node.value) is int:
            value: int = node.value

            def apply_const(n: ast.AST, new: int = value + 1) -> None:
                assert isinstance(n, ast.Constant)
                n.value = new

            yield idx, f"{value} -> {value + 1}", apply_const
        elif isinstance(node, ast.Return) and node.value is not None:

            def apply_ret(n: ast.AST) -> None:
                assert isinstance(n, ast.Return)
                n.value = ast.Constant(value=None)

            yield idx, "return value -> None", apply_ret


def generate(path: Path, rel: str, lines: set[int]) -> list[Mutant]:
    text = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    mutants = []
    for idx, desc, apply in _candidates(tree, lines):
        clone = copy.deepcopy(tree)
        target = list(ast.walk(clone))[idx]
        apply(target)
        line = getattr(target, "lineno", 0)
        mutants.append(Mutant(rel, line, desc, ast.unparse(ast.fix_missing_locations(clone))))
    return mutants


def run_mutation(config: Config, base: str, limit: int) -> list[Mutant]:
    """Mutate changed lines in non-test Python files and run the first suite on each."""
    if not config.suites:
        raise PawlError("mutate needs at least one [[suite]]")
    suite = config.suites[0]
    root = config.root
    top = toplevel(root)
    mb = merge_base(root, base)
    clean = run_suite(suite, root)
    mutants: list[Mutant] = []
    pre = prefix(root)
    for status, changed in changed_files(top, mb):
        # Only files under the Pawl root; test patterns are root-relative.
        rel = root_relative(changed, pre)
        if rel is None or status == "D" or not rel.endswith(".py"):
            continue
        if matches_any(rel, config.guard.tests):
            continue
        diff = diff_text(top, mb, changed)
        lines = changed_lines(diff) if status == "M" else set(range(1, 100000))
        mutants += generate(top / changed, changed, lines)
    mutants = mutants[:limit]
    for mutant in mutants:
        path = top / mutant.path
        original = path.read_text(encoding="utf-8")
        try:
            path.write_text(mutant.source, encoding="utf-8")
            try:
                result = run_suite(suite, root)
            except ParseError:
                mutant.status = "killed"  # the suite could not even run
                continue
            killed = bool(result.failing - clean.failing) or result.collected < clean.collected
            mutant.status = "killed" if killed else "survived"
        finally:
            path.write_text(original, encoding="utf-8")
    return mutants
