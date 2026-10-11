# zs_pawl_episodes

Local Databricks Declarative Automation Bundle scaffold for pawl episode data. Nothing is deployed.

## Local commands

```bash
cd data/databricks
python scripts/build_fixtures.py
python scripts/build_manifest.py
pytest -q
databricks bundle validate -t dev
```

Notes:
- workspace_host and catalog have no default. Provide workspace_host at login.
- schema defaults to pawl_dev.
- Fixtures are generated only by scripts/build_fixtures.py from real repo sources.
- Tests skip when fixtures are absent.
- Source paths are relative to the repo root, two directories above this bundle root.
- Tables: raw_episode, validated_episode, curated_episode, quarantine_episode.
- Serverless job uses environments with environment_key default and client "2".
- No clusters and no new_cluster are declared.
