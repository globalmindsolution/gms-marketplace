#!/usr/bin/env bash
# A /acs:ship run over EVAL-1 that stopped part-way: every step
# workflows/ship.yaml lists before create-pr is recorded `completed` --
# analyze-requirements through run-e2e-tests, the cap implemented and left
# uncommitted on main (ADR-0127: only create-pr branches and commits), the
# review passed -- and then the session ended. Each step was recorded through the plugin's own writers: `acs step
# start`, the step's result document, and its post-hook (review-code's
# derives verifier_passed from the verdict). The steps that owe nothing carry
# their no-op outcome, as ship-ticket-to-pr's calibration plays them.
#
# `/acs:ship EVAL-1` must RESUME: the run's cursor is create-pr, so that is
# the one step it runs -- which fails at its critical gh base detection
# before any push -- and nothing earlier is re-run. The per-step state files
# carry one invocation each; a restarted pipeline appends a second.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_ticket "Cap the customer page size at 100" task false \
  "GET /customers must not return more than 100 customers per page: list_customers refuses a larger limit instead of silently serving it."
acs_local_origin

acs() { python3 "$ACS_SCRIPTS/acs.py" "$@"; }
run="$ACS_PARTITION/runs/EVAL-1"

start() { acs step start --step "$1" --ticket EVAL-1 > /dev/null 2>&1; }
finish() {  # finish STEP OUTCOME [STATES_JSON]
  local step="$1" outcome="$2" states="${3:-}" out=""
  if [ -z "$states" ]; then states='{}'; fi
  if [ -n "$outcome" ]; then out="\"outcome\": \"$outcome\", "; fi
  printf '{"status": "completed", %s"summary": "%s: done", "states": %s, "findings": [], "errors": []}\n' \
    "$out" "$step" "$states" > "$run/steps/$step/result.json"
  python3 "$ACS_SCRIPTS/post-$step.py" --result-file "$run/steps/$step/result.json" > /dev/null
}

start analyze-requirements; finish analyze-requirements ""
start create-impl-plan; finish create-impl-plan ""
start create-api-contract; finish create-api-contract no_surface_owed
start create-test-docs; finish create-test-docs no_cases_owed

start code
# /acs:code leaves the change uncommitted on main (ADR-0127).
cat > src/shop/__init__.py <<'PY'
PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def health():
    return "ok"


def list_customers(offset=0, limit=PAGE_SIZE):
    if limit > MAX_PAGE_SIZE:
        raise ValueError("limit must be at most %d" % MAX_PAGE_SIZE)
    return {"items": [], "offset": offset, "limit": limit}
PY
cat > tests/test_customers.py <<'PY'
import pytest

from shop import list_customers


def test_limit_of_100_is_allowed():
    assert list_customers(limit=100)["limit"] == 100


def test_limit_above_100_is_refused():
    with pytest.raises(ValueError, match="100"):
        list_customers(limit=101)
PY
finish code implemented "{\"files\": [\"src/shop/__init__.py\", \"tests/test_customers.py\"], \"tasks_implemented\": [\"page-size-cap\"], \"tests\": {\"passed\": 3, \"failed\": 0}, \"docs_updated\": []}"

start review-code
sha="$(acs changes snapshot | python3 -c 'import json, sys; print(json.load(sys.stdin)["tree"])')"
mkdir -p "$run/steps/review-code/iter-1"
printf '{"skill": "review-code", "run_id": "EVAL-1", "iteration": 1, "reviewed_sha": "%s", "passed": true, "findings": []}\n' \
  "$sha" | tee "$run/steps/review-code/iter-1/verdict.json" > "$run/steps/review-code/verdict.json"
finish review-code passed

start create-e2e-tests
start docs-sync
finish create-e2e-tests no_e2e_owed
finish docs-sync ""
start run-e2e-tests; finish run-e2e-tests nothing_to_run
