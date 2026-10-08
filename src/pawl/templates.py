"""Files that ``pawl init`` can write. Kept identical to integrations/ (a test checks).

The workflow pins Pawl by version and by the sha256 of its PyPI files. The
version always comes from ``pawl.__version__``; ``pawl init --github`` fills in
the hashes from PyPI, and the copy in integrations/ carries placeholders that
make pip fail until they are replaced.
"""

from __future__ import annotations

from pawl import __version__

PLACEHOLDER_WHEEL = "REPLACE_WITH_WHEEL_SHA256"
PLACEHOLDER_SDIST = "REPLACE_WITH_SDIST_SHA256"

_WORKFLOW = """\
# Pawl ratchet gate. Make the "pawl" job a required status check on main.
# Actions are pinned by commit SHA. Dependabot keeps the pins current.
name: pawl

on:
  pull_request:
    types: [opened, synchronize, reopened, labeled, unlabeled]
  push:
    branches: [main]

permissions:
  contents: read

concurrency:
  group: pawl-${{{{ github.ref }}}}
  cancel-in-progress: true

jobs:
  pawl:
    runs-on: ubuntu-latest
    timeout-minutes: 60
    permissions:
      contents: read
      pull-requests: write # only for the report comment
    env:
      BASE_REF: ${{{{ github.base_ref }}}}
      EVENT: ${{{{ github.event_name }}}}
      PR_NUMBER: ${{{{ github.event.pull_request.number }}}}
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0
          persist-credentials: false
      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
        with:
          python-version: "3.12"
      # Pawl is installed first, into its own virtual environment, from exact
      # hashes. The project's dependencies cannot replace or shadow it, and the
      # steps below call it by absolute path. pawl-gate has no dependencies.
      - name: Install Pawl (hash-pinned, own venv)
        run: |
          python -m venv "$RUNNER_TEMP/pawl-venv"
          cat > "$RUNNER_TEMP/pawl-requirements.txt" <<'REQ'
          pawl-gate=={version} \\
              --hash=sha256:{wheel_sha256} \\
              --hash=sha256:{sdist_sha256}
          REQ
          "$RUNNER_TEMP/pawl-venv/bin/python" -m pip install --require-hashes --no-deps \\
            --only-binary :all: -r "$RUNNER_TEMP/pawl-requirements.txt"
          echo "PAWL=$RUNNER_TEMP/pawl-venv/bin/pawl" >> "$GITHUB_ENV"
      - name: Install the project
        run: |
          python -m pip install --upgrade pip
          # Replace with your project's install step so tests can import it.
          if [ -f pyproject.toml ]; then pip install -e .; fi
      - name: Pawl check (gate definition from the base branch)
        run: |
          if [ "$EVENT" = "pull_request" ]; then
            "$PAWL" check --ci --trusted-ref "origin/$BASE_REF"
          else
            "$PAWL" check --ci
          fi
      - name: Pawl guard (tamper detection and test replay)
        if: always() && github.event_name == 'pull_request'
        run: |
          "$PAWL" guard --ci --replay --base "origin/$BASE_REF"
      - name: Post the report on the pull request
        if: always() && github.event_name == 'pull_request'
        continue-on-error: true # fork PRs get a read-only token
        env:
          GH_TOKEN: ${{{{ github.token }}}}
        run: |
          "$PAWL" report --format md > pawl-report.md
          gh pr comment "$PR_NUMBER" --body-file pawl-report.md --edit-last \\
            || gh pr comment "$PR_NUMBER" --body-file pawl-report.md
"""


def github_workflow(
    version: str = __version__,
    wheel_sha256: str = PLACEHOLDER_WHEEL,
    sdist_sha256: str = PLACEHOLDER_SDIST,
) -> str:
    """Render the GitHub workflow for one exact, hash-pinned Pawl release."""
    return _WORKFLOW.format(version=version, wheel_sha256=wheel_sha256, sdist_sha256=sdist_sha256)


GITHUB_WORKFLOW = github_workflow()
