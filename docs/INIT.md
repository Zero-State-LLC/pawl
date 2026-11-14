# Portable setup (PAWL-005 implementation proposal)

Activate the target project's environment before running Pawl. Pawl may be
installed separately with pipx or in its own virtual environment. The default
generated command is `["python", "-m", "pytest", "-q"]`; both initialization
and later checks resolve Python from the target environment's PATH.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install pytest
# Install the project's test dependencies, then run your installed Pawl:
pawl init
```

`pawl init --python python3` selects a different executable name.
`--python .venv/bin/python` selects a project-relative interpreter.
An explicit absolute path is accepted and reported as nonportable. Existing
configurations are not migrated automatically.

Initialization probes the target interpreter and pytest before measuring.
A missing runner exits 3. Incomplete collection, failed hash lookup, or a
write failure exits 2. Known ordinary test failures can still become initial
debt; collection failures and order-dependent outcomes cannot.

For `init --github`, network hash lookup must succeed or the operator must
supply both `--wheel-sha256` and `--sdist-sha256` from a verified release.
No placeholder workflow is committed by init. Explicit hashes allow offline
generation. Review the generated project installation step before adopting
the workflow; validated language-specific install recipes remain open work.

Existing config, baseline, and workflow files require `--force` to replace.
The debt file is preserved and appended. Generated files are staged before
commit; ordinary write errors restore prior bytes and file modes and remove
new generated files. Linked destinations are rejected. An incomplete rollback
is reported as an error. This is not crash recovery for power loss or process
kill, and it cannot undo arbitrary side effects from project test commands.

This proposal is blocked on the existing-test amendments listed in
[the onboarding review](../specs/005-promotion-hardening/onboarding-review.md).
