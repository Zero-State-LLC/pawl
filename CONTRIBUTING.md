# Contributing

Thanks for helping. Pawl is small on purpose: standard library only, Python
3.11 or later, and every feature must catch a real failure mode.

## Set up

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pre-commit install   # optional
```

## Before you open a pull request

```bash
make check     # ruff, ruff format --check, mypy --strict, pytest with coverage
pawl check     # the repository gates itself
```

- Add or update tests for every behavior change. Do not edit or delete
  existing tests to make a change pass; if a test is wrong, say why in the PR.
- Add an entry under `[Unreleased]` in CHANGELOG.md.
- Keep docs plain and short. No em dashes.
- Changes to `pawl.toml`, `pawl.baseline.json`, `PAWL_DEBT.md`, or
  `.github/` need a code owner's review and, for gate changes, the
  `pawl-approved` label.

## Design rules

- Fail closed. If Pawl cannot tell, it exits 2, never 0.
- No runtime dependencies.
- The gate must not trust the branch it is judging. Anything that weakens the
  trusted-ref model needs a design note in DESIGN.md.
- New detection rules need a benchmark scenario in `benchmarks/corpus.py`
  showing what they catch and a clean scenario showing they do not fire on
  legitimate work.

Pawl gates this repository too. Adding a detection pattern to `guard.py` or a
cheat to `benchmarks/corpus.py` puts that pattern in the diff, so `pawl
guard` flags it as `SUSPICIOUS_CODE`. That is expected; a maintainer reviews
and applies the `pawl-approved` label.

## Agents

Coding agents working in this repository follow [AGENTS.md](AGENTS.md).

## Releases

Maintainers bump the version in `pyproject.toml` and `src/pawl/__init__.py`,
move `[Unreleased]` entries under the new version, and tag `vX.Y.Z`.
