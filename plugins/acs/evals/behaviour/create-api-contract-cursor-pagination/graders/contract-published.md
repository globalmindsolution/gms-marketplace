---
type: file_exists
path: docs/architecture/lld/customer-listing/EVAL-1/api-contract.md
---

The coordinator's Publish step copies the verified draft to the change's
design record (`acs.py artifacts show` reports `paths["api-contract.md"]`
under `docs/architecture/lld/customer-listing/EVAL-1/` — ADR-0128), where `/acs:create-test-docs` and `/acs:review-code`
read it. A run that settled `no_surface_owed`, or left the draft only in the
workspace, writes nothing here.
