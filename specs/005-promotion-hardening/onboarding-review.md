# T07-T08: concrete onboarding amendment for owner review

Base: core implementation `a69f56ae4ed2f2ea4ef230521c5591ec90d966a8` (PR #44).
Branch: `harden/005-portable-init-20261114`.

The implementation uses portable target Python selection, explicit overrides,
runner diagnostics, pre-write hash resolution, staged setup files, rollback on
ordinary write errors, overwrite protection, and incomplete-collection refusal.
Thirteen added tests cover these paths. Existing test lines remain untouched.

Two existing tests require behavior that R05-R06 explicitly replace:

| Existing test in tests/test_supply_chain.py | Conflict | Required amendment |
| --- | --- | --- |
| test_init_github_pins_the_passed_hashes | Requires initialization host's absolute Python path | Assert portable `python`; preserve all workflow hash assertions |
| test_init_github_offline_writes_placeholders_and_warns | Requires exit 0 and placeholder workflow on failed lookup | Assert exit 2, no generated files, actionable explicit-hash instructions |

Apply only after the owner authorizes changes to these existing test assertions.
The old test names remain in this minimal patch to preserve baseline IDs.

```diff
--- a/tests/test_supply_chain.py
+++ b/tests/test_supply_chain.py
@@
-import sys
@@
-    assert f'command = [{json.dumps(sys.executable)}, "-m", "pytest", "-q"]' in cfg
+    assert 'command = ["python", "-m", "pytest", "-q"]' in cfg
@@
-    assert main(args) == 0
-    wf = (repo / ".github" / "workflows" / "pawl.yml").read_text(encoding="utf-8")
-    assert wf == GITHUB_WORKFLOW
-    assert "placeholder hashes" in capsys.readouterr().out
+    assert main(args) == 2
+    assert not (repo / "pawl.toml").exists()
+    assert not (repo / "pawl.baseline.json").exists()
+    assert not (repo / "PAWL_DEBT.md").exists()
+    assert not (repo / ".github").exists()
+    assert "--wheel-sha256 and --sdist-sha256" in capsys.readouterr().out
```

After review: apply this exact amendment, rerun make check, then use only the
tightening `pawl update --ci` workflow to add the new test IDs. Verify no old
IDs disappear, run pawl check, and obtain required gate-file owner review.
Never loosen the baseline to hide the two deliberate specification conflicts.

Scope limits: this is the setup transaction slice. It does not complete A28's
fresh Python/JS generated-workflow qualification, crash recovery, M2's bounded
execution, or promotion readiness. Test-command side effects are outside the
generated-file transaction. Runtime verification uses the resolved executable
for initialization while persisting the portable command for future hosts.

## Verification at this checkpoint

2026-11-14 UTC, Python 3.12.14 with the pinned development constraints.
Ruff lint and formatting and strict Mypy pass. Full make check: 282 passed,
2 failed, no skips, 90.27% coverage. Both failures are exactly the two legacy
assertions listed above. Real Go and Rust adapter tests pass.

The 13 new setup tests pass. An additional smoke check created two actual
virtual environments with access to the same pinned pytest dependencies,
initialized a project using environment A, copied it without bytecode caches,
deleted A and the original project, then ran check using environment B. Both
commands exited 0 with the unchanged portable config. This verifies runtime
selection across paths; it is not independent fresh-host dependency installation.

`pawl check --ci --json` fails on the two NEW_FAILURE entries plus the 13
UNBASELINED_TESTS additions. No baseline update was attempted with known failing
legacy assertions, and no test was skipped, changed, or quarantined. The branch
is intentionally blocked, not a successful implementation claim or release.
Per AGENTS.md, this conflict is escalated and implementation stops pending
owner authorization of the exact existing-test amendments above. No PR is
opened for this red branch because make check must pass before a PR.
