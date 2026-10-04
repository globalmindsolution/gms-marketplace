---
type: file_exists
path: docs/architecture/lld/checkout-with-card-payments/EVAL-1/design.md
---

The coordinator's Publish step copies the reviewed draft to the change's
design record (`acs.py artifacts show` reports `paths["design.md"]` =
`docs/architecture/lld/checkout-with-card-payments/EVAL-1/design.md`, the
ticket's feature filing it — ADR-0128), which is what the `design_approved` predicate and
`/acs:code` look for. A draft left only in the workspace partition gates
nothing.
