"""Files that ``pawl init`` can write. Kept identical to integrations/ (a test checks).

The workflow pins Pawl by version and by the sha256 of its PyPI files. The
version always comes from ``pawl.__version__``; ``pawl init --github`` fills in
the hashes from PyPI, and the copy in integrations/ carries placeholders that
make pip fail until they are replaced.

Reporting is split out of the gate. The "pawl" job checks out and runs
candidate code, so it holds a read-only token: it renders the report and
uploads it as an artifact. The "report" job downloads that artifact and posts
the comment. It runs no candidate code and does not check out the repository,
so it is the only job granted pull-requests: write.
"""

from __future__ import annotations

from pawl import __version__

PLACEHOLDER_WHEEL = "REPLACE_WITH_WHEEL_SHA256"
PLACEHOLDER_SDIST = "REPLACE_WITH_SDIST_SHA256"

_WORKFLOW = """\
# Pawl ratchet gate. Make the "pawl" job a required status check on main.
# Actions are pinned by commit SHA. Dependabot keeps the pins current.
#
# Reporting is split out of the gate. The "pawl" job checks out and runs
# candidate code, so it holds a read-only token (contents: read only): it
# renders the report and uploads it as an artifact. The "report" job downloads
# that artifact and posts the comment. It runs no candidate code and does not
# check out the repository, so it is the only job granted pull-requests: write.
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
      - name: Pawl guard (tampering detection and test replay)
        if: always() && github.event_name == 'pull_request'
        run: |
          "$PAWL" guard --ci --replay --base "origin/$BASE_REF"
      - name: Render the report
        if: always() && github.event_name == 'pull_request'
        run: |
          "$PAWL" report --format md > "$RUNNER_TEMP/pawl-report.md"
          printf '%s\\n' "$PR_NUMBER" > "$RUNNER_TEMP/pawl-pr-number.txt"
      - uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2
        if: always() && github.event_name == 'pull_request'
        with:
          name: pawl-report
          path: |
            ${{{{ runner.temp }}}}/pawl-report.md
            ${{{{ runner.temp }}}}/pawl-pr-number.txt
          if-no-files-found: warn
          retention-days: 3

  report:
    needs: pawl
    if: always() && github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    timeout-minutes: 5
    permissions:
      contents: read
      pull-requests: write # the only job that may comment on the PR
    env:
      PR_NUMBER: ${{{{ github.event.pull_request.number }}}}
    steps:
      # No checkout and no candidate code: this job only fetches the report
      # artifact the "pawl" job produced, then posts it.
      - uses: actions/download-artifact@9000827ccba6bdab643e8b6fd33ac0654aef8333 # v8.0.2
        with:
          name: pawl-report
          path: ${{{{ runner.temp }}}}
      - name: Post the report on the pull request
        continue-on-error: true # fork PRs get a read-only token
        env:
          GH_TOKEN: ${{{{ github.token }}}}
        run: |
          gh pr comment "$PR_NUMBER" --repo "$GITHUB_REPOSITORY" \\
            --body-file "$RUNNER_TEMP/pawl-report.md" --edit-last \\
            || gh pr comment "$PR_NUMBER" --repo "$GITHUB_REPOSITORY" \\
              --body-file "$RUNNER_TEMP/pawl-report.md"
"""


def github_workflow(
    version: str = __version__,
    wheel_sha256: str = PLACEHOLDER_WHEEL,
    sdist_sha256: str = PLACEHOLDER_SDIST,
) -> str:
    """Render the GitHub workflow for one exact, hash-pinned Pawl release."""
    return _WORKFLOW.format(version=version, wheel_sha256=wheel_sha256, sdist_sha256=sdist_sha256)


GITHUB_WORKFLOW = github_workflow()
