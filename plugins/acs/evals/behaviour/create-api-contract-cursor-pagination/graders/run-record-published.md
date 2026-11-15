---
type: file_exists
path: docs/architecture/lld/customer-listing/EVAL-1/api-contract.md
---

The coordinator publishes the verified run record to the change's Design
folder (`acs.py artifacts show` reports `paths["api-contract.md"]` under
`docs/architecture/lld/customer-listing/EVAL-1/` -- ADR-0128; the team
setting shares run documents), where /acs:create-impl-plan,
/acs:create-test-docs and /acs:review-code read it.
