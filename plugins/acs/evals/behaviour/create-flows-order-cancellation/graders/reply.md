---
type: llm
---

PASS if the final reply reports the cancel-order flow (a sequence diagram,
with the refund through the payments gateway for a paid order) and the
order's state machine gaining placed -> cancelled and paid -> cancelled
written under docs/architecture/lld/orders/flows/ for EVAL-1, and that the
documents are left as local uncommitted changes
for the user to review and commit, and does not claim component documents.
FAIL if it reports writing code, component or class documents, api/ or
data/ documents, a transition from shipped or delivered to cancelled,
committing or pushing them or opening a PR, or asks the user a question
the request already answered.

That no code, migration or DDL was written is the file graders' to check on
disk; the reply need not say so, only never claim the opposite.
