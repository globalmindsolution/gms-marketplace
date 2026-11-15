---
type: file_exists
path: docs/development/customer-listing/EVAL-1/analysis/README.md
---

The coordinator's Publish step copies the reviewed draft folder to the run's
Development folder, `docs/development/<feature>/<ticket-id>/analysis/`
(ADR-0128, ADR-0133): a run on a ticket is a Development run, and the ticket
traces to the `customer-listing` feature, so `acs.py artifacts show` reports
`paths["analysis.md"]` as that folder's README.md. A draft left only in the
workspace partition, one long `analysis.md` in place of the folder, or an
analysis written anywhere else -- the retired `docs/tickets/EVAL-1/` included
-- is not what the next steps (`/acs:create-api-contract`,
`/acs:create-impl-plan`) read.
