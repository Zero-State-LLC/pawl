# Pawl contract for agents

Put this in the project's AGENTS.md (or the equivalent instructions file).

```markdown
## Tests and the Pawl gate

- The specification takes priority over the tests. If a test contradicts the
  spec, first finish everything the spec asks for, leave that one test
  failing, then run `pawl escalate "<what conflicts>" --test <id>` and stop.
  Do not edit the test, special-case the code, or rewrite the spec or its
  docstring to make the conflicting test pass.
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
```

Why this wording: in an exploratory study, one sentence saying the spec takes
priority over the tests eliminated cheating across 280 episodes
(arXiv:2610.04793). An explicit escalation channel, rather than forcing the
agent to either cheat or fail, cut reward hacking from 23.6% to 5.3%
(arXiv:2608.29460). In Pawl's own live trial (BENCHMARKS.md), an earlier
wording that said only "escalate and stop" made agents give up before doing
the possible work; "first finish everything the spec asks for" fixed that.
