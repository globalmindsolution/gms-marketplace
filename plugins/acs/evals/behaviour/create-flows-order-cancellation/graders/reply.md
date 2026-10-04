---
type: llm
---

PASS if the final reply reports the cancel-order flow (a sequence diagram,
with the refund through the payments gateway for a paid order) and the
order's state machine gaining placed -> cancelled and paid -> cancelled
written under docs/architecture/lld/orders/flows/ for EVAL-1, says no code
was written and that the documents are left uncommitted (or recorded for the
later publish), and does not claim component documents.
FAIL if it reports writing code, component or class documents, api/ or
data/ documents, a transition from shipped or delivered to cancelled,
committing to main, or asks the user a question the request already
answered.
