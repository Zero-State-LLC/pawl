# Quality report v0.1 (pawl)
- 74/74 rows passed DQ, 0 quarantined.
- Small sample: 12 live episodes from one model and one task. This is a smoke test, not a rate.
- The split is very uneven (val 2, test 6) because there are only 32 scenario groups. v0.2 needs more tasks and exploit families before held-out metrics mean anything.
- No hook logs exist yet (`.pawl/hook-log.jsonl`). The parser is in place and tested on synthetic dicts only.
- Every human_disposition is null. Danny or a reviewer must label the LIVE episodes before any of them is used as a training label.
