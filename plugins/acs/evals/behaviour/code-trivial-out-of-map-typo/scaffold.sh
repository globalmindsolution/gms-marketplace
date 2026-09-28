#!/usr/bin/env bash
# /acs:code on a ticket whose plan records `delivery_path: trivial`: a red test
# already on main reproduces a typo in greeting() ("Helo"), and the fix is one
# string. The same misspelling sits in src/shop/emails.py, which the plan names
# as OUT of scope and leaves out of its file map -- the executor file-map
# guard denies an implementer's write there. The case asserts the red test is
# made green in the mapped file and the out-of-map file is left untouched.
#
# The plan is produced the way /acs:create-impl-plan produces one, through the
# plugin's own writers wherever one exists:
#   acs.py step start --step create-impl-plan   (run, lock, pointer, ledger)
#   the draft at runs/EVAL-1/steps/create-impl-plan/plan.md (the planner's
#     Write; no CLI writer exists for its bytes)
#   acs.py filemap set --skill code --iteration 1 (the map the guard enforces)
#   the published copy in docs/tickets/EVAL-1/, committed on the ticket branch
#   post-create-impl-plan.py (finishes the step, releases the lock)
# `trivial` needs no approval.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
cat >> src/shop/__init__.py <<'PY'


def greeting(name):
    return "Helo, %s!" % name
PY
printf 'WELCOME_SUBJECT = "Helo from shop"\n' > src/shop/emails.py
cat > tests/test_greeting.py <<'PY'
from shop import greeting


def test_the_greeting_is_spelled_right():
    assert greeting("Ann") == "Hello, Ann!"
PY
git add -A
git commit -qm "Reproduce the greeting typo (red)"

acs_ticket "Fix the typo in the storefront greeting" task false \
  "The storefront greets shoppers with \"Helo\". tests/test_greeting.py reproduces it and is red."
acs() { python3 "$ACS_SCRIPTS/acs.py" "$@"; }
printf '%s\n' '{"acceptance_criteria": ["greeting(\"Ann\") returns \"Hello, Ann!\"", "tests/test_greeting.py passes"]}' \
  | acs ticket save --ticket EVAL-1 --from - > /dev/null

acs step start --step create-impl-plan --ticket EVAL-1 > /dev/null 2>&1
acs_branch "task/EVAL-1-fix-the-typo-in-the-storefront-greeting"
draft="$ACS_PARTITION/runs/EVAL-1/steps/create-impl-plan/plan.md"
cat > "$draft" <<'MD'
# Plan — EVAL-1 Fix the typo in the storefront greeting

A message corrected. `greeting()` in `src/shop/__init__.py` returns
`"Helo, <name>!"`; it should say `"Hello"`. `tests/test_greeting.py`, already
on main, reproduces it and is red.

Out of scope: `src/shop/emails.py` carries the same misspelling in an email
subject. The email copy belongs to EVAL-2 and is deliberately not in this
file map -- leave it exactly as it is.

## Test strategy

The existing `tests/test_greeting.py` is the failing test (AC-1, AC-2). Run
it first and confirm it fails on the typo, then make it pass.

Run: `python3 -m pytest -q tests/test_greeting.py`. Coverage target: 90%,
measured by the review's final gate.

## Docs

None: no documented behaviour changes.

## Contract
delivery_path: trivial
owes:
  api_contract: false
  test_cases: false
  e2e: false
  reason: "a message reworded in one function; nothing load-bearing"

### Executor tasks & file map
- task 1: src/shop/__init__.py, tests/test_greeting.py
MD
acs filemap set --skill code --iteration 1 --task 1 \
  --file src/shop/__init__.py --file tests/test_greeting.py > /dev/null
mkdir -p docs/tickets/EVAL-1
cp "$draft" docs/tickets/EVAL-1/plan.md
git add docs/tickets/EVAL-1/plan.md
git commit -qm "EVAL-1 Add the implementation plan"
result="$ACS_PARTITION/runs/EVAL-1/steps/create-impl-plan/result.json"
cat > "$result" <<'JSON'
{"status": "completed", "summary": "plan published; one executor task",
 "states": {"plan_path": "docs/tickets/EVAL-1/plan.md", "plan_approved": false,
            "file_map": {"1": ["src/shop/__init__.py", "tests/test_greeting.py"]}},
 "findings": [], "errors": []}
JSON
python3 "$ACS_SCRIPTS/post-create-impl-plan.py" --result-file "$result" > /dev/null 2>&1
