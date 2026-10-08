from __future__ import annotations

from pathlib import Path

from pawl.templates import GITHUB_WORKFLOW

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".venv", "__pycache__", "work", ".mypy_cache", ".ruff_cache", ".pytest_cache"}
TEXT = {".py", ".md", ".toml", ".yml", ".yaml", ".json", ".sh", ".txt", ".cfg"}


def test_integration_workflow_matches_init_template() -> None:
    assert (ROOT / "integrations" / "github" / "pawl.yml").read_text() == GITHUB_WORKFLOW


def test_no_em_dashes_in_repo() -> None:
    files = [
        p
        for p in ROOT.rglob("*")
        if p.is_file() and p.suffix in TEXT and not SKIP_DIRS.intersection(p.parts)
    ]
    bad = [
        str(p.relative_to(ROOT))
        for p in files
        if "\u2014" in p.read_text(encoding="utf-8", errors="ignore")
    ]
    assert bad == []
