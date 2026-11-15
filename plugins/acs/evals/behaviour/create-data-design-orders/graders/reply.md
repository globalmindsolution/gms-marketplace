---
type: llm
---

PASS if the final reply reports that the orders feature's logical ERD and
physical schema were written under docs/architecture/lld/orders/data/ for
EVAL-1 -- naming the order and order-line entities or tables -- and left as
local uncommitted changes for the user to review and commit, and
points to a next step such as /acs:create-flows or
/acs:analyze-requirements.
FAIL if it reports writing a migration, DDL or code, changing the HLD,
writing api/ or flows/ documents, committing or pushing them or opening a
PR, or asks the user a question the request already answered.

That no code, migration or DDL was written is the file graders' to check on
disk; the reply need not say so, only never claim the opposite.
