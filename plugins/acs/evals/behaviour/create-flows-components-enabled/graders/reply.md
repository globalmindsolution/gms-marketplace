---
type: llm
---

PASS if the final reply reports the cancel-order flow, the order's state
machine and the orders component document (its internals and its classes)
written under docs/architecture/lld/orders/ for EVAL-1, with no code
written and the documents left uncommitted or recorded for the later
publish.
FAIL if it says component or class documents were skipped or not enabled,
reports writing code, api/ or data/ documents, or asks the user a question
the request already answered.
