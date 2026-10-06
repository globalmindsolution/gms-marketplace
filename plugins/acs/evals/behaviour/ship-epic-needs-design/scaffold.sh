#!/usr/bin/env bash
# An EPIC, EVAL-1 ("Checkout with card payments", needs_design true), minted
# through new-ticket.py in a repo with a PRD and architecture docs. No design
# exists and no children have been fanned out.
#
# "Epics are never shipped." Every implementation step's pre-hook carries the
# epic brake, so ship's first step (analyze-requirements) is refused with the
# whole Design-phase path: /acs:create-tech-design EVAL-1, then
# /acs:breakdown-ticket EVAL-1, then /acs:ship <child-id> per child. ship surfaces that
# pointer verbatim and STOPS -- it does not run the design, mint children, or
# implement anything on the epic itself.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_prd
acs_architecture
acs_ticket "Checkout with card payments" epic true \
  "Shoppers pay for their basket by card at checkout (PRD F2): a checkout endpoint charges the card through the payments gateway, records the order, and returns its id."
