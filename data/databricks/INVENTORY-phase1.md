# Phase 1 source inventory (generated 2026-10-10 PT, read-only)

## Slang: local files

| path | bytes | sha256 | mtime | rows | class | rights / sensitivity |
|---|---|---|---|---|---|---|
| `/workspace/vernacular-ingest/data/vernacular.sqlite3` | 8982528 | `540daeeb591d5961d0d3b71246b1d4ec9a39ec7670baf686893ee007507dd855` | 2026-10-10 12:17 PT | observations=1991; candidates=1102; terms=180; term_variants=190; events=259; receipts=345; outbox=162; failed_ingests=66; meaning_history=83; term_metrics_v1=41; observation_sense_v1=881; term_metrics_v2=185; operator_definitions=2; term_meaning_v1=41; term_meaning_v2=185; term_discovery_v1=138; observation_sense_anchored_v1=21; operator_term_status=2; term_dictionary_v1=185 | SoT: OBSERVED posts + INFERRED/model tables + 2 human rulings | X post text + author_id (PII/handle); X ToS redistribution unknown |
| `/workspace/hyperlex-harvest/exports-for-notion/vernacular.sqlite3` | 2863104 | `c48d99afda1d57579a1f144e3a4367d42c893c25618b34f45d9ab262dbea36ce` | 2026-10-10 01:12 PT | observations=990; candidates=598; terms=38; term_variants=48; events=107; receipts=224; outbox=145; failed_ingests=49; meaning_history=51 | stale copy (subset, older schema) | same as SoT |
| `/workspace/vernacular-ingest/out/hyperlex_candidates.jsonl` | 204588 | `a32135c7bb530d292117d93114b4171bee93b88dac4d2dc5d5e75095aa96a568` | 2026-10-10 12:17 PT | 295 | INFERRED (license "operator-local; labels INFERRED") | X-derived text; redistribution unknown |
| `/workspace/vernacular-ingest/out/hyperlex_usage.jsonl` | 118746 | `973b61e2c71f63cfdead3013127f5c92fcf23974fa56028304e81708c7b9c497` | 2026-10-10 12:17 PT | 295 | INFERRED usage packets | X-derived text |
| `/workspace/Hyperlex-readme/data/hyperlex_4333_dump.jsonl` | 2399813 | `b6867a4f441197b78dbfea71a8936894c62f8fa3b4343dc093043e6069e67d7e` | 2026-10-10 01:12 PT | 5019 | mixed: operator-attested/local, label OBSERVED on 374, INFERRED 54, rest unlabeled | licenses operator-local/attested; row-level splits |
| `/workspace/deliverables/hyperlex-census/step4-20260925/holdout-manifest-v2.json` | 51075 | `a9282566dd93be9df84a53fab1103297ca0741b31829f2a6e628a1d37568f83b` | 2026-10-10 01:13 PT |  | holdout manifest / scores (metrics, not labels) | no PII |
| `/workspace/deliverables/hyperlex-rc1/prereg-manifest/holdout-manifest-rc1.json` | 6496 | `ba01894fad6ce5e451b136fa60b30e67d23cf0be2668b983fba986a2e218b407` | 2026-10-10 01:13 PT |  | holdout manifest / scores (metrics, not labels) | no PII |
| `/workspace/deliverables/hyperlex-rc2/rc2-result/holdout-manifest-v2.SCORED_SPENT.json` | 51070 | `4db62c0dbea852f7d7c6113b39aec06da322a08cd60147ea2f5f88fb329d0c0c` | 2026-10-10 01:13 PT |  | holdout manifest / scores (metrics, not labels) | no PII |
| `/workspace/deliverables/hyperlex-rc2/rc2-result/holdout-v2-rc2-per-row.json` | 27373 | `36d0e860f38a3ddd1530f00af66571aee20a5a32c2e2e19685fb13bbbd727aa0` | 2026-10-10 01:13 PT |  | holdout manifest / scores (metrics, not labels) | no PII |
| `/workspace/mirror/repo-files/holdout-manifest-rc1.json` | 6496 | `ba01894fad6ce5e451b136fa60b30e67d23cf0be2668b983fba986a2e218b407` | 2026-10-10 01:13 PT |  | holdout manifest / scores (metrics, not labels) | no PII |
| `/workspace/vernacular-ingest/data/hyperlex-backfill/2026/2026-01.json` | 3062 | `fe5957eac0bbba8f010be58e64285d5b5c7b5910c0e2c45325a360352f493d1e` | 2026-10-10 01:07 PT |  | INFERRED synthetic monthly backfill | no PII |
| `/workspace/vernacular-ingest/data/hyperlex-backfill/2026/2026-02.json` | 2705 | `ace7f5297b4c62d0f1c12f88c19678947716fecae58381b9da4dfc6dcfbd553b` | 2026-10-10 01:07 PT |  | INFERRED synthetic monthly backfill | no PII |
| `/workspace/vernacular-ingest/data/hyperlex-backfill/2026/2026-03.json` | 2518 | `4f8bde0d24798eabb3c97d669e9e206c5a377374b576f8d1942ea27a1e1723ed` | 2026-10-10 01:07 PT |  | INFERRED synthetic monthly backfill | no PII |
| `/workspace/vernacular-ingest/data/hyperlex-backfill/2026/2026-04.json` | 2424 | `72d5ef84178e787b7190c977f2fb2e7adc0ab03d4facbbec11542d817c698180` | 2026-10-10 01:07 PT |  | INFERRED synthetic monthly backfill | no PII |
| `/workspace/vernacular-ingest/data/hyperlex-backfill/2026/2026-05.json` | 2456 | `94d6f1ebbc3443dca586224f34e71205118e7958b9d2119fa94f12bc1e897921` | 2026-10-10 01:07 PT |  | INFERRED synthetic monthly backfill | no PII |
| `/workspace/vernacular-ingest/data/hyperlex-backfill/2026/2026-06.json` | 2410 | `7503de573d0815322a183afe46d585470a9e19388a43a1729c5a0f9c48408fef` | 2026-10-10 01:07 PT |  | INFERRED synthetic monthly backfill | no PII |
| `/workspace/vernacular-ingest/data/hyperlex-backfill/2026/2026-07.json` | 2419 | `2641d202670f23ce09b29374a739284bc982dc76b7855ceb0d4ca24a99a8eff3` | 2026-10-10 01:07 PT |  | INFERRED synthetic monthly backfill | no PII |
| `/workspace/vernacular-ingest/data/hyperlex-backfill/2026/2026-08.json` | 2375 | `c7f04a775e73f3aae0ce1aef0cfb39a80bd255c912bf5d2ec6a364e561d31202` | 2026-10-10 01:07 PT |  | INFERRED synthetic monthly backfill | no PII |

Morpheus mirror files (`/workspace/mirror/home/morpheus/.hyperlex/hyperlexical/`): harvest_unbind_observed_mw.jsonl 893 rows sha256 d23539f2f50c2c45..., ingest_candidates.jsonl 4297 rows sha256 a6533160ec5286df... (full hashes in slang_files run).

## Slang: Notion (read-only, fetched 2026-10-10 ~17:55 PT)

| object | url | last edited / newest row | rows | export content sha256 | verdict |
|---|---|---|---|---|---|
| DB Vernacular Intelligence (terms) | https://www.notion.so/ceadff3632ec418296eff02bdf17816f | newest row created 2026-09-26 23:50 PT | 44 | 37ad9bd436655529c69ec0dc165d63f8fb6a314fc52c6db296646fac05dd2614 (sorted JSON of all 44 SQL rows) | stale mirror (SQLite has 180 terms) |
| DB Vernacular Events | https://www.notion.so/3c9257864ecc42f6b6199e31c6b40829 | newest row created 2026-09-26 23:50 PT | 120 | 4e8d5199... covers first 100 rows only (SQL page cap) | stale mirror (SQLite 259 events); has Source Post ID/URL (X refs) |
| Page Vernacular, Operator rulings (2026-09-25) | https://app.notion.com/p/3e63e8ba2f5c81a588cef3368c1f9914 | 2026-09-25 11:51 PT | n/a | fetch sha256 9c409af2af9f64e7... (prefix) | human-ruling record (Danny, rule metrics-rule-v1.4); authoritative for rules, SQLite operator_* tables hold 2 rulings |
| Page Hyperlex + Vernacular export 2026-09-10 | https://app.notion.com/p/3d83e8ba2f5c81248ae5ed44bf38f2ee | 2026-09-12 22:07 PT | n/a | 91e0ca4385a4ed1b... (prefix) | stale export index (pointer page) |

Other Notion slang pages found (not fetched in full; specs/receipts, not data): Adversarial Slang Mutation Grammar (3d23e8ba...), ABX Memetic History Seed Corpus (39c3e8ba...), Daily Native Signal Forage receipts, Hyperstition scans, Naming lock. Vault rule: Notion slang consoles are NOT live SoT.

## Pawl

| path (repo Zero-State-LLC/pawl @ 286e0c0) | bytes | sha256 | rows | class |
|---|---|---|---|---|
| `benchmarks/results.json` | 51092 | `c7d5d151a34e7796477559fc044f6dd268027ebb273f40f11adbd33de886170a` |  | SYNTHETIC scripted scenarios (62 rows, 32 scenarios x clean/debt base) |
| `benchmarks/fixtures/p0_reports.json` | 1980 | `901081eee1c3b740953a08b2cb73b59fd05e0ba10d55a26853e80941f74d012e` | list[13] | SYNTHETIC parser fixtures (13) |
| `benchmarks/live_transcripts/meta.json` | 184 | `0f24ef24a4ab9252d5229f36303ac02869560f67e458a4f546d6a4415904dfe9` |  | LIVE transcript (deepseek-v4.1-flash, 2026-10-08) |
| `benchmarks/live_transcripts/pawl-1.json` | 14353 | `8d999b8385848e254012b48a57bdd9400736562f893c4d0be2016911afb2eb7a` |  | LIVE transcript (deepseek-v4.1-flash, 2026-10-08) |
| `benchmarks/live_transcripts/pawl-2.json` | 10293 | `71ede6462b40e3c96033a99baa6c117a4147ddea89f858fd81352949e9e56779` |  | LIVE transcript (deepseek-v4.1-flash, 2026-10-08) |
| `benchmarks/live_transcripts/pawl-3.json` | 11128 | `027998a042294b0bab59b35f5cee8a483321df9a48871cc6a50867e8071ff416` |  | LIVE transcript (deepseek-v4.1-flash, 2026-10-08) |
| `benchmarks/live_transcripts/pawl-4.json` | 10668 | `196c04db7728f04bba833b28ed10f3079b04179acd098dc7655a0052747a4623` |  | LIVE transcript (deepseek-v4.1-flash, 2026-10-08) |
| `benchmarks/live_transcripts/pawl-v1-1.json` | 15693 | `4ab92bdb554141ea905e21e0fb3020d5fb8ada38b7404fc8875f8ed4014706ba` |  | LIVE transcript (deepseek-v4.1-flash, 2026-10-08) |
| `benchmarks/live_transcripts/pawl-v1-2.json` | 15438 | `d746d04733cab63fb6550df111284b05f17c1569391433a422540ccae15173d4` |  | LIVE transcript (deepseek-v4.1-flash, 2026-10-08) |
| `benchmarks/live_transcripts/pawl-v1-3.json` | 14441 | `c9f64fc949a0035d2d1c81f1491a98cdd048e8637d0943c0663159b5a88f3c06` |  | LIVE transcript (deepseek-v4.1-flash, 2026-10-08) |
| `benchmarks/live_transcripts/pawl-v1-4.json` | 15978 | `9cdb41c540bbd9b4f66ee507a7f4658d8c64388ffb5dce8224f094f091902a91` |  | LIVE transcript (deepseek-v4.1-flash, 2026-10-08) |
| `benchmarks/live_transcripts/plain-1.json` | 15930 | `91c8b2d2df49f3962ac515bd24a5ef66bf5a07c7edb09458e1d562e49a2da24b` |  | LIVE transcript (deepseek-v4.1-flash, 2026-10-08) |
| `benchmarks/live_transcripts/plain-2.json` | 18125 | `e50fb030cc8416a2bf46ed6d879c67868cec275fa25268c563811469375d23e9` |  | LIVE transcript (deepseek-v4.1-flash, 2026-10-08) |
| `benchmarks/live_transcripts/plain-3.json` | 20365 | `f6cb291b3c6f0a7bb3315770509cf53579250a85e2953e90849afcdaf3fb963c` |  | LIVE transcript (deepseek-v4.1-flash, 2026-10-08) |
| `benchmarks/live_transcripts/plain-4.json` | 16306 | `1fa329790fd378d72daee2b1fd09522bb141fea4de627be8317dfc74e5b34bb2` |  | LIVE transcript (deepseek-v4.1-flash, 2026-10-08) |
| `docs/evidence/p0-check-20261010.json` | 932 | `b5a3b8175736386c20c23aecba373dc070c4305d2d0a775155844dbdd2986009` |  | gate/evidence report (pawl self-gate, 2026-10-10) |
| `docs/evidence/p0-effectiveness-20261010.json` | 53368 | `552a05f9cff9e18c33e99c1e1f1f52092499ff7dd5a7d8db8a881c5eda646b12` |  | gate/evidence report (pawl self-gate, 2026-10-10) |
| `docs/evidence/p0-guard-20261010.json` | 466 | `cfa9802227275e18c7bda041f29e2a15d2762390dd8be3ab1c8183abf2f49cca` |  | gate/evidence report (pawl self-gate, 2026-10-10) |
| `docs/evidence/p0-repo-settings-20261010.json` | 4249 | `4194638b49163abffd4b01bc97f8da72a4cdeaf05c04b5a747113ada145e25b3` |  | gate/evidence report (pawl self-gate, 2026-10-10) |
| `pawl.baseline.json` | 16557 | `7d4ab3e386cf47c77b7456817094c5e1e04f789d65efa86844edc94be11a7744` |  | config/baseline |
| `pawl.contracts.json` | 293 | `8ceccd9fbef8751427cde97fb2c95eb35c81a9c280e4130adcf7ca41191bead7` |  | config/baseline |

Also: benchmarks/live_trial.md (12 LIVE episode rows, total trial spend $0.1147 / 83 calls); no CONTEXT.md exists in pawl at origin/main; no hook-log.jsonl exists anywhere on the box (format only, docs/HOOKS_PROVENANCE.md); .pawl/last-report.json found only in other checkouts (pawl-020, argotide, abraxas-pawl-seed), not inventoried as episodes.
