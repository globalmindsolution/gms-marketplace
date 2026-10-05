---
type: file_exists
path: docs/development/customer-listing/EVAL-1/analysis.md
---

The coordinator's Publish step copies the verified draft to the run's
Development folder, `docs/development/<feature>/<ticket-id>/` (ADR-0128): a
run on a ticket is a Development run, and the ticket traces to the
`customer-listing` feature, so `acs.py artifacts show` reports
`paths["analysis.md"]` there. A draft left only in the workspace partition,
or an analysis written anywhere else -- the retired `docs/tickets/EVAL-1/`
included -- is not what the next gates (`/acs:create-api-contract`,
`/acs:create-impl-plan`) look for.
