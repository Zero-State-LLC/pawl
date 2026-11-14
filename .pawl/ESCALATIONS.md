# Escalations

Agents record spec or test conflicts here. A human resolves each one and changes 'open' to 'resolved'.


## 2026-11-14 06:19 UTC open

- Test: `tests/test_supply_chain.py::test_init_github_pins_the_passed_hashes`
- Why: PR53 hosted guard job 132358529372 replays the old absolute-interpreter assertion against the already owner-approved portable init contract. Current candidate tests and trusted-base check pass. Independent reviewer policy is absent on the trusted base; migration must be reviewed and activated there before replay can accept this intentional assertion change. No waiver or label was applied.

## 2026-11-14 06:19 UTC open

- Test: `tests/test_supply_chain.py::test_init_github_offline_writes_placeholders_and_warns`
- Why: PR53 hosted guard job 132358529372 replays the old offline-success placeholder assertion against the already owner-approved transactional failure contract. Current candidate tests and trusted-base check pass. Resolve the independent reviewer identity and reviewed scoped migration on the trusted base; keep replay failures and protected-spec review blocks enforced.
