---
type: llm
---

PASS if the final reply reports that the orders feature's logical ERD and
physical schema were written under docs/architecture/lld/orders/data/ with no
ticket -- naming the order and order-line entities or tables and a migration
outline -- says they are documents only (no migration or code written) and
left as local uncommitted changes, and points to a next step such as
/acs:create-flows orders or /acs:create-ticket.
FAIL if it asks for a ticket id or says one is required, reports creating a
ticket, reports writing a migration, DDL or code, changing the HLD, writing
api/ or flows/ documents, committing or pushing them or opening a PR, or asks
the user a question the request already answered.
