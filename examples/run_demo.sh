#!/usr/bin/env bash
# Walk through Pawl on the demo project: a pass, a regression, a collection
# drop, a weakened test, and a protected-contract rewrite. Runs in a temporary
# copy; nothing here changes.
set -u
here="$(cd "$(dirname "$0")" && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
cp -r "$here/demo/." "$work/"
cd "$work"
export PYTHONDONTWRITEBYTECODE=1

# Debian/Ubuntu hosts often ship only ``python3``. The demo suite command uses
# ``python``; provide a shim when needed so the walkthrough stays portable.
if ! command -v python >/dev/null 2>&1; then
  if ! command -v python3 >/dev/null 2>&1; then
    echo "error: need python or python3 on PATH" >&2
    exit 2
  fi
  mkdir -p "$work/.bin"
  ln -s "$(command -v python3)" "$work/.bin/python"
  export PATH="$work/.bin:$PATH"
fi

git init -q -b main
git add -A
git -c user.email=demo@example.com -c user.name=demo commit -qm "demo base"

step() { printf '\n==> %s\n' "$*"; }
reset() { git checkout -q -- . && git clean -qfd -e .pawl; }

step "1. Clean tree: pawl check passes with 1 known failure"
pawl check; echo "exit $?"

step "2. Regression: subtract breaks"
sed -i.bak 's/    return a - b/    return a + b/' calc/__init__.py && rm -f calc/__init__.py.bak
pawl check; echo "exit $?"
reset

step "3. Collection drop: a test module stops importing"
printf 'import not_a_module\n' >> tests/test_more.py
pawl check; echo "exit $?"
reset

step "4. Weakened test: agent breaks add and edits the test to match"
git checkout -qb agent
sed -i.bak 's/    return a + b/    return abs(a) + abs(b)/' calc/__init__.py
sed -i.bak 's/    assert add(-2, -3) == -5/    assert add(-2, -3) == 5/' tests/test_calc.py
rm -f calc/__init__.py.bak tests/test_calc.py.bak
pawl check; echo "pawl check exit $? (the tests agree with the code)"
pawl guard --base main --replay; echo "pawl guard exit $?"
reset
git checkout -q main

step "5. Protected contract: rewrite a pawl: contract docstring"
git checkout -qb contract-agent
sed -i.bak 's/closed interval \[low, high\]/closed interval [low, high) (exclusive high)/' calc/__init__.py
rm -f calc/__init__.py.bak
pawl guard --base main; echo "pawl guard exit $? (SPEC_AUTHORITY_CHANGED)"
