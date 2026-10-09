"""The machine-readable contract: JSON schema version and exit codes.

Every JSON document Pawl prints (check, guard, update, report, mutate) carries
``schema_version`` and ``exit_code``. Fields are only added within a schema
version; a removal or a change of meaning bumps it. See docs/JSON.md.
"""

from __future__ import annotations

SCHEMA_VERSION = 1

EXIT_PASS = 0
EXIT_FAIL = 1  # a regression, tampering, or a refused update
EXIT_ERROR = 2  # could not measure or could not establish the gate (fail closed)
EXIT_PREFLIGHT = 3  # the environment is wrong; fix it, not the baseline

EXIT = {"pass": EXIT_PASS, "fail": EXIT_FAIL, "error": EXIT_ERROR}


def exit_code_for(status: str) -> int:
    """Exit code for a status. Unknown statuses fail closed."""
    return EXIT.get(status, EXIT_ERROR)
