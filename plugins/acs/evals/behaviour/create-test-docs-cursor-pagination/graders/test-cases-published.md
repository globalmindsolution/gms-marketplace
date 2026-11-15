---
type: file_exists
path: docs/development/customer-listing/EVAL-1/test-cases.md
---

The coordinator's Publish step copies the verified draft to the change's
Development folder (`acs.py artifacts show` reports `paths["test-cases.md"]`
under `docs/development/customer-listing/EVAL-1/` — ADR-0128), which is where `/acs:create-e2e-tests`'s gate and
`/acs:review-code` read it.
