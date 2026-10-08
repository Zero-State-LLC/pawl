# Pawl contract for agents

## Tests and the Pawl gate

- The specification takes priority over the tests. If a test and the spec
  disagree, run `pawl escalate "<what conflicts>" --test <id>` and stop. Do not
  edit the test to match the code, and do not edit the code to satisfy a test
  you believe is wrong.
- You are not done until `pawl check` exits 0. Do not report success while it
  is red, and do not skip it.
- Never edit these files: `pawl.toml`, `pawl.baseline.json`, `PAWL_DEBT.md`,
  `.pawl/`, `.github/workflows/`, `CODEOWNERS`, `conftest.py`, and the test
  runner config (`pytest.ini`, `pyproject.toml` tool tables, `package.json`
  scripts, `Cargo.toml`). Existing test lines are read-only: add tests, do not
  change them.
- `pawl update` is for tightening only. Loosening the baseline
  (`pawl update --loosen`) and `pawl quarantine` are for humans.
- If the gate blocks you and you cannot fix the code, escalate and stop. Do
  not look for another way around the gate.

Why this wording: in an exploratory study, one sentence saying the spec takes
priority over the tests eliminated cheating across 280 episodes
(arXiv:2610.04793). An explicit escalation channel, rather than forcing the
agent to either cheat or fail, cut reward hacking from 23.6% to 5.3%
(arXiv:2608.29460). See RESEARCH.md.

## Working on Pawl itself

- Standard library only. No runtime dependencies.
- `make check` (ruff, ruff format, mypy --strict, pytest with coverage) must
  pass before a pull request.
- Every new detection rule needs a scenario in `benchmarks/corpus.py` and a
  clean scenario that it does not flag.
- No em dashes anywhere in the repository.
- Changes to gate files need a code owner's review and the `pawl-approved`
  label.
