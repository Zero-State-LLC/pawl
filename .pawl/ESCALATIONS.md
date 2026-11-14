# Escalations

Agents record spec or test conflicts here. A human resolves each one and changes 'open' to 'resolved'.


## 2026-11-14 03:23 UTC resolved

- Test: `tests/test_supply_chain.py::test_init_github_pins_the_passed_hashes`
- Why: PAWL-005 R05-R06 replace two legacy assertions: test_init_github_pins_the_passed_hashes requires an absolute host Python path; test_init_github_offline_writes_placeholders_and_warns requires successful placeholder output offline. The implementation follows the spec; both existing tests remain unchanged and fail. Exact proposed amendments and verification are in specs/005-promotion-hardening/onboarding-review.md. Owner authorization is required before editing these existing test lines.

- Resolution: Daniel authorized the exact proposed amendments by replying "Continue" to their review request on 2026-11-13 Pacific Time. Applied only those assertions, preserving test IDs and hash checks. No baseline loosening or approval override is authorized by this resolution.
