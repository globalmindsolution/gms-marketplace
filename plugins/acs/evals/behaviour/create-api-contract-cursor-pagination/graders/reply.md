---
type: llm
---

PASS if the final reply reports that the customers interface document under
docs/architecture/lld/customer-listing/api/ was revised for EVAL-1 -- GET
/customers gaining a cursor and next_cursor, invalid_cursor as a 400 -- and
versioned (proposed, v2), that the run record api-contract.md was published,
that the change is backward compatible with offset kept, that it wrote
documents only (no OpenAPI or code) left uncommitted, and points to a next
step such as /acs:create-impl-plan.
FAIL if it reports writing code, tests or a machine-readable contract,
declares a breaking change or a /v2, says it needs a plan first, commits or
pushes, or asks the user a question the request already answered.
