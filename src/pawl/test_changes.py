"""Classify test edits without assuming added lines preserve assertion execution."""

from __future__ import annotations

import ast
import copy
from dataclasses import dataclass

from pawl.errors import PawlError


@dataclass(frozen=True)
class TestChange:
    review_required: bool
    full_replay: bool
    reason: str


def _same(before: ast.AST, after: ast.AST) -> bool:
    return ast.dump(before, include_attributes=False) == ast.dump(after, include_attributes=False)


def _header(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> str:
    header = copy.copy(node)
    header.body = []
    return ast.dump(header, include_attributes=False)


def _restricted_assert(node: ast.stmt) -> bool:
    if not isinstance(node, ast.Assert):
        return False
    allowed = (
        ast.Assert,
        ast.Name,
        ast.Load,
        ast.Constant,
        ast.Tuple,
        ast.List,
        ast.Set,
        ast.Dict,
        ast.Compare,
        ast.BoolOp,
        ast.UnaryOp,
        ast.BinOp,
        ast.cmpop,
        ast.boolop,
        ast.unaryop,
        ast.operator,
    )
    return all(isinstance(child, allowed) for child in ast.walk(node))


def _terminal_asserts(
    before: ast.FunctionDef | ast.AsyncFunctionDef, after: ast.FunctionDef | ast.AsyncFunctionDef
) -> bool:
    if type(before) is not type(after) or _header(before) != _header(after):
        return False
    count = len(before.body)
    return (
        len(after.body) > count
        and all(_same(a, b) for a, b in zip(before.body, after.body[:count], strict=True))
        and all(_restricted_assert(item) for item in after.body[count:])
    )


def _bindings(tree: ast.Module) -> set[str]:
    names = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
    }
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.alias):
            names.add(node.asname or node.name.split(".")[0])
    return names


def _new_test(node: ast.stmt, names: set[str]) -> bool:
    if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
        return False
    if node.name in names or node.decorator_list or node.returns or node.type_comment:
        return False
    args = node.args
    if args.defaults or any(x is not None for x in args.kw_defaults):
        return False
    params = [*args.posonlyargs, *args.args, *args.kwonlyargs]
    params += [x for x in (args.vararg, args.kwarg) if x is not None]
    return not any(arg.annotation for arg in params) and not getattr(node, "type_params", [])


def classify(before: str, after: str, path: str) -> TestChange:
    """Return review/scope decisions; malformed Python is never a clean edit."""
    if not path.endswith(".py"):
        same = before == after
        return TestChange(not same, not same, "non-Python test edit requires review")
    try:
        old, new = ast.parse(before), ast.parse(after)
    except (SyntaxError, ValueError, RecursionError) as exc:
        raise PawlError(f"cannot classify test source {path!r}: {exc}") from exc
    if _same(old, new):
        return TestChange(False, False, "no executable change")
    names = _bindings(old)
    index = 0
    review = False
    full = False
    for node in new.body:
        prev = old.body[index] if index < len(old.body) else None
        if prev is not None and _same(prev, node):
            index += 1
            continue
        if _new_test(node, names):
            assert isinstance(node, ast.FunctionDef)
            names.add(node.name)
            # New tests may affect collection or shared state: never narrow.
            full = True
            continue
        if (
            isinstance(prev, (ast.FunctionDef, ast.AsyncFunctionDef))
            and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and prev.name == node.name
        ):
            index += 1
            if prev.name.startswith("test_") and _header(prev) == _header(node):
                review = review or not _terminal_asserts(prev, node)
            else:
                review = full = True
            continue
        # Imports, class changes, bindings, fixtures, or ambiguous ordering.
        return TestChange(True, True, "shared binding, fixture, or module execution changed")
    if index != len(old.body):
        return TestChange(True, True, "existing executable statements removed or reordered")
    return TestChange(review, full, "test execution changed" if review else "bounded test addition")
