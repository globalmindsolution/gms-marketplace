---
type: llm
---

PASS if the final reply reports that the orders feature's logical ERD and
physical schema were written under docs/architecture/lld/orders/data/ for
EVAL-1 -- naming the order and order-line entities or tables and a migration
outline -- says they are documents only (no migration or code written) and
left uncommitted (or recorded for the later publish) because no ticket
branch is checked out, and points to a next step such as /acs:create-flows
or /acs:analyze-requirements.
FAIL if it reports writing a migration, DDL or code, changing the HLD,
writing api/ or flows/ documents, committing to main, or asks the user a
question the request already answered.
