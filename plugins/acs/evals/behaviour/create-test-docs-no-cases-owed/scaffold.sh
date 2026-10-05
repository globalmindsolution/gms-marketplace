#!/usr/bin/env bash
# create-test-docs (nothing owed): the shop repo and a DOCS-ONLY task,
# EVAL-1 "Document how to run the tests", minted through new-ticket.py with
# --docs-only true. The working tree (main, uncommitted -- ADR-0127) carries its published plan, whose
# Contract block owes no test cases (`test_cases: false`, with a reason), and
# the create-impl-plan step is RUN through the plugin's own writers (`acs step
# start`, the draft, `acs.py filemap set`, result.json,
# post-create-impl-plan.py) because the no-op is read from the run's own plan.
# The create-test-docs pre-hook then records the step completed with
# `outcome: no_cases_owed` and refuses the Skill call (exit 2).
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
python3 "$ACS_SCRIPTS/new-ticket.py" --title "Document how to run the tests" --type task \
  --needs-design false --docs-only true \
  --description "New contributors cannot find how to run the test suite. Add a Running the tests section to CONTRIBUTING.md." > /dev/null
printf '%s' '{"acceptance_criteria": [
  "CONTRIBUTING.md has a Running the tests section naming the pytest command and the 90% coverage floor"
]}' | python3 "$ACS_SCRIPTS/acs.py" ticket save --ticket EVAL-1 --from - > /dev/null
mkdir -p docs/development/developer-docs/EVAL-1
cat > docs/development/developer-docs/EVAL-1/plan.md <<'MD'
# Plan — EVAL-1: Document how to run the tests

A docs-only ticket (docs_only true): CONTRIBUTING.md gains a "Running the
tests" section. No behaviour changes, so no new tests: the one full-suite run
proves nothing broke. coverage_target: "n/a — docs_only".

## Contract
delivery_path: trivial
owes:
  test_cases: false
  e2e: false
  reason: "docs-only: CONTRIBUTING.md prose; no behaviour to test"

### Executor tasks & file map
- task 1: CONTRIBUTING.md
MD
step="$ACS_PARTITION/runs/EVAL-1/steps/create-impl-plan"
python3 "$ACS_SCRIPTS/acs.py" step start --step create-impl-plan --ticket EVAL-1 > /dev/null 2>&1
cp docs/development/developer-docs/EVAL-1/plan.md "$step/plan.md"
python3 "$ACS_SCRIPTS/acs.py" filemap set --skill code --iteration 1 --task 1 --file CONTRIBUTING.md > "$step/filemap.out"
python3 - "$step" <<'PY'
import json, sys
step = sys.argv[1]
file_map = json.load(open(step + "/filemap.out"))["tasks"]
json.dump({"status": "completed", "summary": "plan reviewer passed on iteration 1; plan published",
           "states": {"plan_path": "docs/development/developer-docs/EVAL-1/plan.md", "plan_approved": False,
                      "file_map": file_map},
           "findings": [], "errors": []}, open(step + "/result.json", "w"))
PY
rm "$step/filemap.out"
python3 "$ACS_SCRIPTS/post-create-impl-plan.py" --result-file "$step/result.json" > /dev/null
