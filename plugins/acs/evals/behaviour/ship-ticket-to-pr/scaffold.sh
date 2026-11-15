#!/usr/bin/env bash
# One small, well-specified task for /acs:ship to drive end to end: EVAL-1,
# minted through new-ticket.py and given its acceptance criteria through
# `acs ticket save` (the writer /acs:create-ticket itself uses). No run is
# started -- ship starts it -- and nothing is on a branch yet.
#
# The pipeline is workflows/ship.yaml's: analyze-requirements through
# create-pr. gh cannot reach a forge in the run (and the remote resolves to
# the local bare repository, so even an authenticated gh finds no GitHub
# remote), so the last step, create-pr, fails at its critical base detection
# BEFORE pushing -- and ship must stop there and report it, never merge.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_ticket "Cap the customer page size at 100" task \
  "GET /customers must not return more than 100 customers per page: list_customers refuses a larger limit instead of silently serving it."
acs_local_origin

ticket_json="$(mktemp)"
python3 "$ACS_SCRIPTS/acs.py" ticket show --ticket EVAL-1 > "$ticket_json"
python3 - "$ticket_json" <<'PY'
import json, sys
path = sys.argv[1]
with open(path, encoding="utf-8") as fh:
    ticket = json.load(fh)
ticket = ticket.get("ticket", ticket)
ticket["acceptance_criteria"] = [
    "list_customers(limit=101) raises ValueError naming the maximum of 100",
    "list_customers(limit=100) still returns a page with limit 100",
    "the default page size stays 20",
]
with open(path, "w", encoding="utf-8") as fh:
    json.dump(ticket, fh)
PY
python3 "$ACS_SCRIPTS/acs.py" ticket save --ticket EVAL-1 --from "$ticket_json" > /dev/null
rm -f "$ticket_json"
