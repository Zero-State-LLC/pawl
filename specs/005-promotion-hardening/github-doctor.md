# T13 GitHub observations and conservative control assessment

Status: implemented for review, stacked on PR #51. Full CI certification remains
open; this extends the offline checker with explicit authenticated reads.

## Contract

Online calls require --online, explicit --repository OWNER/REPO and --branch,
and GH_TOKEN or GITHUB_TOKEN in the trusted launcher's environment. Targets are
not taken from candidate remotes/config. Tokens never enter subprocesses,
reports, logs or exception text. The client performs GET requests only, directly
to api.github.com using standard HTTPS certificate validation. It does not use
proxy environment variables, follow redirects, or follow server pagination URLs.

Bodies are capped at 1 MiB with JSON depth 64 and duplicate-key/nonfinite rejection.
Socket operations time out after five seconds; a 15-second elapsed budget is
checked between body reads. DNS resolution and response-header handling are not
a hard real-time sandbox. Non-200 status, timeout, malformed/oversized body,
unsupported compression and incomplete rule pages remain UNKNOWN. Raw API error
bodies and credential values are not emitted. No persistent response cache exists.

The selected branch and commit SHA are observed first, then classic branch
protection and active branch rules. A last-push control may PASS only with an
explicit positive classic policy, positive review count, admin enforcement and
explicitly empty user/team/app review bypass lists. Current-base checks may PASS
only with strict mode, admin enforcement, no listed bypass, and the exact
operator-supplied context/app binding. Missing fields do not become defaults.

A known false classic setting becomes FAIL only if the complete active-rules
response is empty. Alternative rulesets, incomplete pages and access denials
prevent claims that no alternative enforcement exists. Ruleset bypass/applicability
semantics are not certified by this slice. Independent human/agent identity,
CODEOWNERS coverage, workflow implementation and release controls still need
separate evidence. Overall CI readiness therefore cannot become READY here.

## Validation and live limits

Recorded-response tests cover clean strict policies and denied/redirected reads,
partial rules, bypasses, wrong app binding, malformed/deep/large/duplicate JSON,
credential injection, response deadlines, fixed-host GET behavior, offline
network prohibition and absence of tokens in diagnostics. Existing tests remain
unchanged. The new HTTP cases are also enumerated in benchmarks/corpus.py.
Full make check passed with 477 tests, no skips, 90.28% coverage, lint,
formatting and strict typing, using real Go and Rust toolchains. Baseline and
self-gate counts are recorded in the PR. The broader effectiveness scenario
list is unchanged and was not rerun. Large-payload test cases have explicit
stable IDs. The final baseline is generated in a clean checkout from PR #51
with every committed ID retained; an unpublished oversized auto-ID artifact
from the development checkout is excluded. Guard against PR #51 requires owner
review for four specification authority changes; no override was used.

Live connected-source evidence is in operator-ci-review.md. Classic protection
was denied with 403 and the effective-branch-rules route was unavailable through
the connector. No real token was exported from the connector or supplied to the
new runtime client; authenticated transport behavior is covered by fixtures,
not claimed as a live end-to-end success. No settings were changed.

## Primary API references

- https://docs.github.com/en/rest/branches/branch-protection#get-branch-protection
- https://docs.github.com/en/rest/repos/rules#get-rules-for-a-branch

The API examples support version 2026-03-10. Classic protection reads require
Administration read permission; effective branch rules use Metadata read and
exclude disabled/evaluate rulesets. These endpoint observations do not by
themselves establish operator or publisher independence.
