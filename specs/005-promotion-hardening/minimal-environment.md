# T12 explicit child environments

Status: implemented for review; stacked on PR #49. Not isolated execution.

## Policy

`[execution].environment` defaults to `inherit`. This preserves existing callers'
environment behavior. `minimal` constructs each child environment from the
launcher's PATH (or the platform default if absent), fixed C locale, a fresh
HOME and temporary directory, trusted adapter variables, and `pass_env` names.
The launcher and its executable search path remain trusted inputs.

`pass_env` is an array of at most 256 unique exact ASCII variable names, each
at most 256 characters. Wildcards, invalid types and assignment syntax fail.
Missing names are absent, not synthesized. HOME, TMPDIR, TMP, TEMP and
PAWL_TEST_ORDER are reserved for Pawl and cannot be inherited through this list.
Locale, PATH, credentials and injection variables can be deliberately inherited
by name; such access is a reviewed policy decision, not hidden isolation.

Each command gets private temporary HOME/tmp directories, removed after success,
startup failure, timeout, interruption or output-limit failure. Setup/cleanup
errors fail closed with typed errors. Environment failures during narrowed replay
cannot be retried into a passing result. Candidate config cannot weaken a policy
loaded through `--trusted-ref`. Base-test replay uses its trusted configuration.

Pytest's alternate-order plugin supplies its own temporary PYTHONPATH and order
marker. In minimal mode it appends ambient PYTHONPATH only when explicitly named
in pass_env. Default-order runs do not inherit ambient PAWL_TEST_ORDER.

## Reporting and tests

Check JSON includes environment mode, pass_env names, an explicit sandbox=false
flag, and a limitation statement. Markdown displays the same policy. No policy
report includes variable values. Arbitrary child output is not secret-redacted:
commands given access to credentials can print them or transmit them.

The corpus includes inherited exposure, minimal exclusion and explicit exposure
of a synthetic marker through the real CLI. New tests cover injection variables,
configuration validation, compatibility defaults, fresh directories and cleanup,
preflight, reverse-order pytest, explicit PYTHONPATH, trusted-base policy, and
base-test replay. Existing test lines and repository execution settings remain
unchanged. Full `make check` passed: 410 tests, no skips, 90.05% coverage,
lint, formatting and strict typing, with real Go and Rust toolchains. The
three new environment corpus cases run through the CLI in that suite. The
broader effectiveness scenario list is unchanged and was not rerun. Guard
against PR #49 blocks only the two specification authority changes pending
owner review; no approval override was used. Baseline and final self-gate
results are recorded in the PR.

## Boundaries

This policy does not restrict filesystem reads, processes, network, system-wide
configuration or executable contents. It does not hide the parent's environment
from a same-user process with host inspection access. It does not impose disk
quotas or isolate Git subprocesses used by Pawl itself. Those require the later
controller/worker design. Native Windows remains unqualified. Some toolchains
need explicit cache or toolchain variables; fresh HOME can change behavior.

The intermittent grandchild-timeout test observed during PR #49 qualification
remains an unresolved historical risk. Checks for this slice run sequentially;
passing reruns do not establish that the earlier cause was fixed.
