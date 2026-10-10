# Security policy

## Supported versions

| Version | Supported |
| --- | --- |
| 0.3.x | Yes |
| 0.2.x | Yes until the next minor after 0.3 |
| 0.1.x | No |

## Reporting a vulnerability

Report privately through GitHub: Security > Report a vulnerability on this
repository. Do not open a public issue. Expect an acknowledgment within 5
business days.

## What counts

Pawl is a security control for coding agents, so a gate bypass is a
vulnerability. Examples:

- A change that makes `pawl check --ci --trusted-ref` or `pawl guard --ci`
  pass while a baseline test fails, disappears, or is skipped, or while a gate
  file changed without approval.
- Input (a test report, diff, or config) that makes Pawl exit 0 when it should
  exit 1, 2, or 3.
- Command injection through `pawl.toml`, test IDs, or hook payloads.

Known limits are listed in docs/ARCHITECTURE_REVIEW.md under "Threats not
covered". Reports about those are welcome but are not treated as
vulnerabilities.
