#!/usr/bin/env bash
# /acs:set-doc-status asked to mark two feature PRDs implemented, when only one
# is (ADR-0146). Both are approved v1. Card checkout's one requirement is
# named by story EVAL-1, whose id leads a merged commit on main: delivered.
# Order tracking's one requirement is named by story EVAL-2, still open: not
# delivered. Tickets are minted through the plugin's own writer. A local bare
# repository stands in for GitHub.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs() { python3 "$ACS_SCRIPTS/acs.py" "$@"; }

acs_repo
acs_moscow_prd
acs design init --status approved docs/product/prd.md docs/product/features/*/prd.md > /dev/null
python3 "$ACS_SCRIPTS/new-ticket.py" --title "Pay by card" --type story \
  --features card-checkout --requirements card-checkout/R1 > /dev/null
python3 "$ACS_SCRIPTS/new-ticket.py" --title "Follow an order" --type story \
  --features order-tracking --requirements order-tracking/R1 > /dev/null
git add -A && git commit -qm "PRD"
git commit -q --allow-empty -m "EVAL-1 Pay by card (#21)"
acs_local_origin
