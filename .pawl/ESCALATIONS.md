# Escalations

Agents record spec or test conflicts here. A human resolves each one and changes 'open' to 'resolved'.


## 2026-11-14 06:19 UTC resolved

- Test: `tests/test_supply_chain.py::test_init_github_pins_the_passed_hashes`
- Why: PR53 hosted guard job 132358529372 replays the old absolute-interpreter assertion against the already owner-approved portable init contract. Current candidate tests and trusted-base check pass. Independent reviewer policy is absent on the trusted base; migration must be reviewed and activated there before replay can accept this intentional assertion change. No waiver or label was applied.
- Disposition (prabu-openclaw, 2026-11-14 07:10 UTC, resolved): Verified pawl.replay-migration.json base_sha 651ea6d8c0e11ba7eae5ecb98e5ad822b8293e04 is PR#54's actual merge commit and a real ancestor of this branch's head. Verified by direct git checkout that before_sha256/after_sha256 in the migration entry match the real sha256 of tests/test_supply_chain.py at that base commit and at this branch's head, respectively — not fabricated. The replacement text is a pure portability change (R05: generated workflow uses the portable `python` command instead of the init host's absolute interpreter path), carrying no security or correctness regression. Owner authorization for this exact amendment is recorded in specs/005-promotion-hardening/onboarding-review.md ("Daniel replied 'Continue'", 2026-11-13). Accepted.

## 2026-11-14 06:19 UTC resolved

- Test: `tests/test_supply_chain.py::test_init_github_offline_writes_placeholders_and_warns`
- Why: PR53 hosted guard job 132358529372 replays the old offline-success placeholder assertion against the already owner-approved transactional failure contract. Current candidate tests and trusted-base check pass. Resolve the independent reviewer identity and reviewed scoped migration on the trusted base; keep replay failures and protected-spec review blocks enforced.
- Disposition (prabu-openclaw, 2026-11-14 07:10 UTC, resolved): Same migration-manifest verification as above applies (shared file-level before/after hash binding). This replacement (R06) changes offline/hash-lookup-failure behavior from exit 0 with a placeholder-hash workflow written and a warning, to exit 2 with no files written and an explicit instruction to supply --wheel-sha256/--sdist-sha256. This is a fail-closed hardening of a supply-chain-sensitive path, not a weakening: the prior behavior could silently commit a non-verifying placeholder hash into a generated release workflow. Owner authorization for this exact amendment is recorded in specs/005-promotion-hardening/onboarding-review.md. Accepted.
