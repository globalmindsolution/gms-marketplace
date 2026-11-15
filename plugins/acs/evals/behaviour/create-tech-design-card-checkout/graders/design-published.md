---
type: file_exists
path: docs/architecture/lld/checkout-with-card-payments/EVAL-1/tech-design.md
---

The coordinator's Publish step copies the reviewed draft to the change's
design record (`acs.py artifacts show` reports `paths["tech-design.md"]` =
`docs/architecture/lld/checkout-with-card-payments/EVAL-1/tech-design.md`, the
ticket's feature filing it — ADR-0128, ADR-0135), which is what the
`design_approved` predicate, `/acs:set-doc-status` and `/acs:code` look for.
A draft left only in the workspace partition is a hand-off nobody can review.
