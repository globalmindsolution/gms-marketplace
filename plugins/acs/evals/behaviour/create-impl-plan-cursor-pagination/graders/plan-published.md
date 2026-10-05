---
type: file_exists
path: docs/development/customer-listing/EVAL-1/plan.md
---

The coordinator's Publish step copies the verified draft to the change's
Development folder, which is where `/acs:code`'s gate looks for it (`acs.py
artifacts show` reports `paths["plan.md"]` under
`docs/development/customer-listing/EVAL-1/`, the ticket's feature filing it —
ADR-0128). A plan left only in the
workspace draft, or written anywhere else, does not open the next gate.
