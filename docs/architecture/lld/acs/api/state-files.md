---
status: "implemented"
version: 1
tickets: []
feature: "acs"
---

# API — Inter-step state files

The canonical `states` keys one step's state file hands the next step's gate.

## Inter-step contract (state files)

The next skill reads only canonical `states` keys — e.g. `/create-pr` gate:
`steps/review-code/state.json`'s `states.verifier_passed == true`; `/merge-pr` gate: a `states.pr`
reference recorded by a COMPLETED step — `gates._pr_recorded_for` reads
`steps/<skill>/state.json` for `create-pr` (and for each `DELIVERY_TICKET_SKILLS`
member — an empty list since ADR-0127), across every run of the ticket, and requires that step's last status to
be `completed`. Full table:
INTERNALS.md "Canonical states keys per skill". Schemas:
`plugins/acs/schemas/*.schema.json`. `code-state.states.plan_approved` is
recorded by `plan-approval.py` and is **not** read by any gate this
release — `/create-pr`'s gate remains the review's `states.verifier_passed ==
true` (MAR-73, slice 3 of MAR-69).
