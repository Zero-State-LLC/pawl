"""Protected normative contracts: spec files, ADRs, and marked docstrings.

A repository's normative text (specs, requirements, ADRs, contract fixtures)
and any Python docstring that carries the ``pawl: contract`` marker are
contracts. Changing one without a commit-bound human approval is reported as
``SPEC_AUTHORITY_CHANGED``.
"""

from __future__ import annotations

import ast
import fnmatch
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pawl import gitutil
from pawl.config import DEFAULT_CONTRACTS
from pawl.errors import ConfigError

REGISTRY = "pawl.contracts.json"
CONTRACT_MARKER = "pawl: contract"
REGISTRY_VERSION = 1

_STATUS_WORDS = {"A": "added", "M": "modified", "D": "deleted", "R": "modified"}


@dataclass
class Change:
    """One changed file: path, Pawl-root-relative path, status, and texts."""

    path: str
    rel: str | None
    status: str
    base_text: str | None
    head_text: str | None


@dataclass
class Moves:
    """Detected contract moves: intact files, escaped files, moved docstrings."""

    files: dict[str, str]
    escaped: dict[str, str]
    docstrings: dict[tuple[str, str], str]
    new_docstrings: set[tuple[str, str]]


def glob_match(path: str, pattern: str) -> bool:
    """Match ``path`` against ``pattern``. A leading ``**/`` also matches at the root."""
    if fnmatch.fnmatchcase(path, pattern):
        return True
    return pattern.startswith("**/") and fnmatch.fnmatchcase(path, pattern[3:])


def matches_any(path: str, patterns: tuple[str, ...] | list[str]) -> bool:
    return any(glob_match(path, pattern) for pattern in patterns)


def _root_relative(path: str, prefix: str) -> str | None:
    """A top-level-relative git path made relative to the Pawl root, or None if outside it."""
    if not prefix:
        return path
    return path[len(prefix) :] if path.startswith(prefix) else None


def file_hash(text: str) -> str:
    """SHA-256 hex digest of ``text`` encoded as UTF-8."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _is_contract(docstring: str) -> bool:
    """True when any stripped line of ``docstring`` is or starts with the marker."""
    return any(line.strip().startswith(CONTRACT_MARKER) for line in docstring.splitlines())


def _docstring_hash(docstring: str) -> str:
    normalized = "\n".join(line.rstrip() for line in docstring.splitlines())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _scan(body: list[ast.stmt], prefix: str, found: dict[str, str]) -> None:
    """Collect marked docstrings from defined names, recursing into their bodies."""
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            qualname = f"{prefix}.{node.name}" if prefix else node.name
            docstring = ast.get_docstring(node, clean=False)
            if docstring is not None and _is_contract(docstring):
                found[qualname] = _docstring_hash(docstring)
            _scan(node.body, qualname, found)


def contract_docstrings(source: str) -> dict[str, str]:
    """Marked docstrings in ``source``: qualified name to hash of the docstring text.

    The module docstring is ``<module>``; nested classes and functions use dotted
    qualified names. Invalid Python yields an empty mapping (nothing to protect).
    """
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return {}
    found: dict[str, str] = {}
    module_docstring = ast.get_docstring(tree, clean=False)
    if module_docstring is not None and _is_contract(module_docstring):
        found["<module>"] = _docstring_hash(module_docstring)
    _scan(tree.body, "", found)
    return found


def detect_moves(
    changes: list[Change], patterns: tuple[str, ...] | list[str] = DEFAULT_CONTRACTS
) -> Moves:
    """Pair deleted contracts with added identical copies, and moved docstrings.

    A deleted file at a protected path paired with an added file whose content hash
    matches is a move; it lands in ``files`` when the new path is still protected and
    in ``escaped`` otherwise. A marked docstring whose hash disappears from one
    changed ``.py`` file and appears with the same qualname and hash in another is a
    move; its new ``(path, qualname)`` is recorded in ``new_docstrings``.
    """
    files: dict[str, str] = {}
    escaped: dict[str, str] = {}
    adds = sorted(
        (c for c in changes if c.status == "A" and c.head_text is not None),
        key=lambda c: c.path,
    )
    used: set[str] = set()
    dels = sorted(
        (c for c in changes if c.status == "D" and c.base_text is not None),
        key=lambda c: c.path,
    )
    for old in dels:
        old_rel = old.rel if old.rel is not None else old.path
        if not (matches_any(old_rel, patterns) or matches_any(old.path, patterns)):
            continue
        digest = file_hash(old.base_text or "")
        for new in adds:
            if new.path in used or new.head_text is None:
                continue
            if file_hash(new.head_text) != digest:
                continue
            new_rel = new.rel if new.rel is not None else new.path
            protected = matches_any(new_rel, patterns) or matches_any(new.path, patterns)
            used.add(new.path)
            if protected:
                files[old.path] = new.path
            else:
                escaped[old.path] = new.path
            break

    removed: list[tuple[str, str, str]] = []
    added: list[tuple[str, str, str]] = []
    for change in changes:
        if not change.path.endswith(".py"):
            continue
        before = contract_docstrings(change.base_text or "")
        after = contract_docstrings(change.head_text or "")
        for qualname, digest in before.items():
            if after.get(qualname) != digest:
                removed.append((change.path, qualname, digest))
        for qualname, digest in after.items():
            if before.get(qualname) != digest:
                added.append((change.path, qualname, digest))
    removed.sort()
    added.sort()
    docstrings: dict[tuple[str, str], str] = {}
    new_docstrings: set[tuple[str, str]] = set()
    taken: set[tuple[str, str]] = set()
    for old_path, qualname, digest in removed:
        for new_path, new_qualname, new_digest in added:
            if new_qualname != qualname or new_digest != digest or new_path == old_path:
                continue
            if (new_path, new_qualname) in taken:
                continue
            taken.add((new_path, new_qualname))
            docstrings[(old_path, qualname)] = new_path
            new_docstrings.add((new_path, qualname))
            break
    return Moves(
        files=files,
        escaped=escaped,
        docstrings=docstrings,
        new_docstrings=new_docstrings,
    )


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def build_registry(
    root: Path, patterns: tuple[str, ...] | list[str] = DEFAULT_CONTRACTS
) -> dict[str, Any]:
    """Hash every tracked contract file and every marked docstring under ``root``."""
    prefix = gitutil.prefix(root)
    files: dict[str, str] = {}
    docstrings: dict[str, str] = {}
    for line in gitutil.git(root, "ls-files").splitlines():
        raw = line.strip()
        if not raw:
            continue
        rel = _root_relative(raw, prefix)
        if rel is None:
            continue
        text = _read_text(root / rel)
        if text is None:
            continue
        if matches_any(rel, patterns):
            files[rel] = file_hash(text)
        if rel.endswith(".py"):
            for qualname, digest in contract_docstrings(text).items():
                docstrings[f"{rel}::{qualname}"] = digest
    return {"pawl_contracts": REGISTRY_VERSION, "files": files, "docstrings": docstrings}


def _string_map(value: Any, where: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ConfigError(f"{REGISTRY}: '{where}' must be an object")
    out: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise ConfigError(f"{REGISTRY}: '{where}' must map strings to strings")
        out[key] = item
    return out


def parse_registry(text: str | None) -> dict[str, Any] | None:
    """Parse registry JSON. A missing registry is None; anything malformed raises."""
    if text is None:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{REGISTRY}: invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{REGISTRY}: must be a JSON object")
    if data.get("pawl_contracts") != REGISTRY_VERSION:
        raise ConfigError(f"{REGISTRY}: 'pawl_contracts' must be {REGISTRY_VERSION}")
    return {
        "pawl_contracts": REGISTRY_VERSION,
        "files": _string_map(data.get("files", {}), "files"),
        "docstrings": _string_map(data.get("docstrings", {}), "docstrings"),
    }


def _registry_entry(registry: dict[str, Any], rel_path: str) -> str | None:
    files = registry.get("files")
    if not isinstance(files, dict):
        return None
    entry = files.get(rel_path)
    return entry if isinstance(entry, str) else None


def _docstring_findings(
    path: str,
    base_text: str | None,
    head_text: str | None,
    moves: Moves | None = None,
) -> list[tuple[str, str]]:
    base_docs = contract_docstrings(base_text or "")
    head_docs = contract_docstrings(head_text or "")
    moved_from = moves.docstrings if moves is not None else {}
    moved_to = moves.new_docstrings if moves is not None else set()
    findings: list[tuple[str, str]] = []
    for qualname in sorted(set(base_docs) | set(head_docs)):
        before = base_docs.get(qualname)
        after = head_docs.get(qualname)
        if before is None:
            if (path, qualname) in moved_to:
                continue
            findings.append((path, f"contract docstring {qualname} added"))
        elif after is None:
            if (path, qualname) in moved_from:
                continue
            findings.append((path, f"contract docstring {qualname} removed"))
        elif before != after:
            findings.append((path, f"contract docstring {qualname} changed"))
    return findings


def contract_findings(
    path: str,
    rel: str | None,
    status: str,
    *,
    base_text: str | None,
    head_text: str | None,
    patterns: tuple[str, ...] | list[str] = DEFAULT_CONTRACTS,
    registry: dict[str, Any] | None = None,
    moves: Moves | None = None,
) -> list[tuple[str, str]]:
    """Findings for one changed file: normative text, docstrings, registry hashes."""
    rel_path = rel if rel is not None else path
    in_pattern = matches_any(rel_path, patterns) or matches_any(path, patterns)
    pattern_reported = in_pattern and status in _STATUS_WORDS
    findings: list[tuple[str, str]] = []
    if pattern_reported:
        if moves is not None and path in moves.escaped:
            target = moves.escaped[path]
            findings.append((path, f"normative contract moved out of protected paths to {target}"))
        elif moves is not None and (path in moves.files or path in moves.files.values()):
            pass
        else:
            findings.append((path, f"normative contract {_STATUS_WORDS[status]}"))
    if rel_path.endswith(".py"):
        findings.extend(_docstring_findings(path, base_text, head_text, moves))
    moved = moves is not None and rel_path in moves.files
    if registry is not None and not pattern_reported and not moved:
        recorded = _registry_entry(registry, rel_path)
        if recorded is not None and (
            status == "D" or head_text is None or file_hash(head_text) != recorded
        ):
            findings.append((path, "registered contract hash mismatch"))
    return findings
