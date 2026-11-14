"""Commit-bound, independently approved assertion replacement for trusted replay.

No replay failure is waived. Approved replacements are applied to base test
source, retaining all statements outside the declared assertion blocks.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import textwrap
from dataclasses import dataclass
from typing import Any

from pawl.baseline import parse_baseline
from pawl.config import CONFIG_NAME, Config, parse_config
from pawl.errors import PawlError
from pawl.gitutil import git, prefix, safe_path, show, toplevel
from pawl.trust import label_approval

REGISTRY = "pawl.replay-migration.json"
MAX_MANIFEST = 262144
MAX_SOURCE = 1048576


class ReplayMigrationError(PawlError):
    code = "REPLAY_MIGRATION_INVALID"


@dataclass(frozen=True)
class ReplayMigration:
    config: Config
    overlays: dict[str, str]
    ids: tuple[str, ...]
    actor: str
    sha: str


def _fail(message: str) -> PawlError:
    return ReplayMigrationError(f"REPLAY_MIGRATION_INVALID: {message}")


def _keys(value: Any, keys: set[str], where: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise _fail(f"invalid fields in {where}")
    return value


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _fail("duplicate JSON key")
        result[key] = value
    return result


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _function(source: str, name: str) -> ast.FunctionDef:
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError) as exc:
        raise _fail("unparseable test source") from exc
    matches = [
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    if len(matches) != 1 or matches[0].decorator_list:
        raise _fail("requires a unique undecorated top-level test function")
    return matches[0]


def _statements(text: Any, *, replacement: bool) -> list[ast.stmt]:
    if not isinstance(text, str) or not text.endswith("\n") or len(text) > 32768:
        raise _fail("assertion block must be bounded text ending with a newline")
    try:
        nodes = ast.parse(textwrap.dedent(text)).body
    except (SyntaxError, ValueError, RecursionError) as exc:
        raise _fail("invalid assertion block") from exc
    if not nodes or not any(isinstance(node, ast.Assert) for node in nodes):
        raise _fail("each block must retain at least one assertion")
    for node in nodes:
        if isinstance(node, ast.Assert):
            continue
        if (
            not replacement
            and isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            continue
        raise _fail("only assertions and old simple local assignments may be replaced")
    return nodes


def _matches(body: list[ast.stmt], nodes: list[ast.stmt]) -> list[int]:
    wanted = [ast.dump(node, include_attributes=False) for node in nodes]
    available = [ast.dump(node, include_attributes=False) for node in body]
    return [i for i in range(len(body) - len(nodes) + 1) if available[i : i + len(nodes)] == wanted]


def replace_block(source: str, candidate: str, function: str, before: str, after: str) -> str:
    """Replace exact complete statements in base source, not whole functions."""
    old_nodes = _statements(before, replacement=False)
    new_nodes = _statements(after, replacement=True)
    if before == after:
        raise _fail("no-op replacement")
    old_function = _function(source, function)
    new_function = _function(candidate, function)
    starts = _matches(old_function.body, old_nodes)
    if len(starts) != 1 or len(_matches(new_function.body, new_nodes)) != 1:
        raise _fail("block must occur exactly once in both declared test functions")
    index = starts[0]
    first, last = old_function.body[index], old_function.body[index + len(old_nodes) - 1]
    assert last.end_lineno is not None
    lines = source.splitlines(keepends=True)
    if "".join(lines[first.lineno - 1 : last.end_lineno]) != before:
        raise _fail("before block does not exactly match complete source lines")
    result = "".join(lines[: first.lineno - 1]) + after + "".join(lines[last.end_lineno :])
    # Reparse and prove the edit did not escape the original function body.
    updated = _function(result, function)
    expected = old_function.body[:index] + new_nodes + old_function.body[index + len(old_nodes) :]
    if [ast.dump(n) for n in updated.body] != [ast.dump(n) for n in expected]:
        raise _fail("replacement escaped its declared statement span")
    old_tree, new_tree = ast.parse(source), ast.parse(result)
    for tree in (old_tree, new_tree):
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == function:
                node.body = []
    if ast.dump(old_tree) != ast.dump(new_tree):
        raise _fail("replacement changed code outside its declared function body")
    return result


def resolve_migration(config: Config, base: str, *, replay: bool) -> ReplayMigration | None:
    try:
        return _resolve_migration(config, base, replay=replay)
    except (OSError, UnicodeError, RecursionError) as exc:
        raise _fail("unreadable or excessively nested migration evidence") from exc


def _resolve_migration(config: Config, base: str, *, replay: bool) -> ReplayMigration | None:
    root, top = config.root, toplevel(config.root)
    pre = prefix(root)
    registry = pre + REGISTRY
    path = safe_path(top, registry)
    if not path.is_file():
        return None
    if path.stat().st_size > MAX_MANIFEST:
        raise _fail("manifest exceeds byte limit")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise _fail("cannot read manifest as UTF-8") from exc
    if text == show(top, base, registry):
        return None  # Consumed migration retained as history, not a standing exemption.
    if not replay:
        raise _fail("a proposed migration requires --replay")
    base_config = show(top, base, pre + CONFIG_NAME)
    if base_config is None:
        raise _fail("migration needs an existing trusted gate")
    trusted = parse_config(base_config, root)
    policy = trusted.guard
    if not policy.approvers or not policy.refuse_pr_author:
        raise _fail("trusted policy must allowlist independent reviewers and refuse PR authors")
    approval, _ = label_approval(policy.approval_label, root, policy.approvers, True)
    if (
        approval is None
        or approval.event != "pull_request"
        or approval.action != "labeled"
        or not approval.run_id.isdecimal()
        or type(approval.pr) is not int
        or approval.pr <= 0
    ):
        raise _fail("requires an independent commit-bound pull-request label event")
    # Bind the manifest to the reviewed head and refuse local edits after approval.
    if git(top, "status", "--porcelain", "--untracked-files=all").strip():
        raise _fail("reviewed candidate must have a clean tracked and untracked worktree")
    if show(top, approval.sha, registry) != text:
        raise _fail("manifest is not the independently reviewed head version")
    try:
        data = json.loads(text, object_pairs_hook=_pairs)
    except (ValueError, RecursionError) as exc:
        raise _fail("invalid JSON") from exc
    data = _keys(data, {"schema_version", "base_sha", "entries"}, "manifest")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise _fail("unsupported schema version")
    if data["base_sha"] != base:
        raise _fail("migration base does not match the replay base")
    entries = data["entries"]
    if not isinstance(entries, list) or not 1 <= len(entries) <= 16:
        raise _fail("expected 1..16 migration entries")
    baseline_text = show(top, base, pre + trusted.baseline)
    if baseline_text is None:
        raise _fail("missing trusted baseline")
    baseline = parse_baseline(baseline_text)
    eligible = {
        test_id
        for suite in trusted.suites
        if suite.adapter == "pytest" and suite.name in baseline.suites
        for test_id in baseline.suites[suite.name].collected_ids
    }
    overlays: dict[str, str] = {}
    ids: list[str] = []
    for raw in entries:
        entry = _keys(
            raw,
            {"path", "function", "before_sha256", "after_sha256", "replacements", "reason"},
            "entry",
        )
        rel, function = entry["path"], entry["function"]
        if not isinstance(rel, str) or not rel.endswith(".py"):
            raise _fail("entry path must name a Python test")
        safe_path(root, rel)
        if not isinstance(function, str) or re.fullmatch(r"test_[A-Za-z0-9_]+", function) is None:
            raise _fail("invalid test function name")
        identity = f"{rel}::{function}"
        if identity not in eligible or identity in ids:
            raise _fail("test must have a unique existing trusted pytest identity")
        if not isinstance(entry["reason"], str) or not 1 <= len(entry["reason"].strip()) <= 2048:
            raise _fail("entry requires a bounded review reason")
        target = pre + rel
        original, candidate = show(top, base, target), show(top, approval.sha, target)
        if original is None or candidate is None or max(len(original), len(candidate)) > MAX_SOURCE:
            raise _fail("missing or oversized test source")
        if digest(original) != entry["before_sha256"] or digest(candidate) != entry["after_sha256"]:
            raise _fail("test source hash mismatch")
        if safe_path(top, target).read_text(encoding="utf-8") != candidate:
            raise _fail("working test differs from reviewed source")
        replacements = entry["replacements"]
        if not isinstance(replacements, list) or not 1 <= len(replacements) <= 16:
            raise _fail("expected 1..16 assertion replacements")
        current = overlays.get(target, original)
        for raw_block in replacements:
            block = _keys(raw_block, {"before", "after"}, "replacement")
            current = replace_block(current, candidate, function, block["before"], block["after"])
        overlays[target] = current
        ids.append(identity)
    return ReplayMigration(trusted, overlays, tuple(ids), approval.actor, approval.sha)
